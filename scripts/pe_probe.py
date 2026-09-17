#!/usr/bin/env python3
"""PyInstaller exe 探针 —— 判断是否 PyInstaller 打包、定位 cookie、报告 Python 版本。

在动手解包前先跑这个：Python 版本决定后续反汇编工具链（3.11 的 pyc 用 3.13 读不了），
而 CArchive / PYZ 的偏移只有解析出 cookie 才知道。

用法：
    python pe_probe.py <exe路径> [--entries N] [--json]
"""
import argparse
import json
import os
import struct
import sys

# PyInstaller 2.0+ 的尾部 cookie 魔数
COOKIE = b"MEI\x0c\x0b\x0a\x0b\x0e"

# CArchive TOC 条目头部长度：4+4+4+4+1+1
TOC_ENTRY_HEADER = 18


def pyver_to_str(pyver):
    """把 PyInstaller 记录的 pyver 整数还原成 Python 版本串。"""
    if pyver >= 100:
        return f"{pyver // 100}.{pyver % 100}"
    return f"0.{pyver}"


def read_toc(f, archive_start, toc_offset, toc_len, limit):
    """读取 CArchive 的 TOC 条目。"""
    entries = []
    f.seek(archive_start + toc_offset)
    count = toc_len // TOC_ENTRY_HEADER
    for _ in range(count):
        head = f.read(TOC_ENTRY_HEADER)
        if len(head) < TOC_ENTRY_HEADER:
            break
        entry_len, entry_pos, csize, usize = struct.unpack("!IIII", head[:16])
        cmprs_flag, type_char = head[16], head[17]
        name_bytes = f.read(entry_len)
        name = name_bytes.rstrip(b"\x00").decode("utf-8", "replace")
        entries.append({
            "name": name,
            "type": chr(type_char),
            "offset": entry_pos,
            "compressed": csize,
            "uncompressed": usize,
            "is_compressed": cmprs_flag == 1,
        })
    return entries[:limit] if limit else entries


def probe(path, limit=20):
    result = {"file": os.path.abspath(path), "is_pyinstaller": False}

    if not os.path.isfile(path):
        result["reason"] = "文件不存在"
        return result

    size = os.path.getsize(path)
    result["size"] = size

    if size < 24:
        result["reason"] = "文件过小，不可能是 PyInstaller 包"
        return result

    with open(path, "rb") as f:
        f.seek(-24, os.SEEK_END)
        cookie = f.read(24)
        if cookie[:8] != COOKIE:
            result["reason"] = "尾部未找到 PyInstaller cookie（可能不是 PyInstaller，或已被加壳）"
            return result

        pkg_len, toc_off, toc_len, pyver = struct.unpack("!IIII", cookie[8:])

        result.update({
            "is_pyinstaller": True,
            "package_length": pkg_len,
            "toc_offset": toc_off,
            "toc_length": toc_len,
            "pyver_raw": pyver,
            "python_version": pyver_to_str(pyver),
            "toc_entry_count": toc_len // TOC_ENTRY_HEADER,
        })

        archive_start = size - pkg_len
        result["carchive_start"] = archive_start

        if archive_start < 0:
            result["reason"] = "package_length 异常，文件可能不完整"
            result["is_pyinstaller"] = False
            return result

        try:
            entries = read_toc(f, archive_start, toc_off, toc_len, limit)
            result["entries"] = entries
            result["has_pyz"] = any(e["type"] == "z" for e in entries)
        except Exception as exc:  # noqa: BLE001
            result["toc_error"] = str(exc)

    return result


def main():
    ap = argparse.ArgumentParser(description="PyInstaller exe 探针")
    ap.add_argument("exe")
    ap.add_argument("--entries", type=int, default=20, help="最多列出多少条 TOC（0 为全部）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = ap.parse_args()

    info = probe(args.exe, limit=args.entries)

    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0 if info["is_pyinstaller"] else 1

    if not info["is_pyinstaller"]:
        print(f"[否] {info['file']}")
        print(f"     {info.get('reason', '未识别为 PyInstaller 包')}")
        return 1

    print(f"[是] PyInstaller 包：{info['file']}")
    print(f"     文件大小      : {info['size']:,} 字节")
    print(f"     打包 Python   : {info['python_version']}  (pyver={info['pyver_raw']})")
    print(f"     CArchive 起点 : {info['carchive_start']:,}")
    print(f"     TOC 条目数    : {info['toc_entry_count']}")
    print(f"     含 PYZ        : {'是' if info.get('has_pyz') else '否（可能已剥离或布局不同）'}")

    if info.get("entries"):
        print("\n     TOC 条目（前若干条）：")
        for e in info["entries"]:
            kind = "PYZ" if e["type"] == "z" else ("PKG" if e["type"] == "s" else e["type"])
            print(f"       [{kind}] {e['name']}  ({e['uncompressed']:,} 字节)")

    print("\n下一步：参见 references/reverse-playbook.md")
    print("  省事路线：pip install pyinstxtractor-ng --target ./_rev -i <腾讯镜像>")
    print("            PYTHONPATH=./_rev python ./_rev/pyinstxtractor_ng.py <exe>")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
