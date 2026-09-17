#!/usr/bin/env python3
"""UTF-8 安全解压 —— 修复中文文件名乱码。

背景：Git Bash 自带的 unzip 不认 zip 的 UTF-8 标志位（flag bit 0x800），
会把中文文件名解成乱码，依赖文件名的程序（如 ffmpeg 读 .webm）会直接崩。
Python zipfile 会正确识别该标志位。本脚本在此基础上再补一层：
对未打标志位的老式 GBK / Big5 包，回退尝试按原编码解码。

用法：
    python safe_unzip.py <zip文件> [-d 目标目录] [--list] [--dry-run]
"""
import argparse
import os
import sys
import zipfile

# 未打 UTF-8 标志位时的回退编码，按可能性排序
FALLBACK_ENCODINGS = ("utf-8", "gbk", "big5", "cp936")


def decode_name(info):
    """解出正确的文件名。zipfile 未识别 UTF-8 标志位时按 CP437 误读，这里补救。"""
    if info.flag_bits & 0x800:
        return info.filename  # 标准 UTF-8，无需处理
    raw = info.filename.encode("cp437", errors="replace")
    for enc in FALLBACK_ENCODINGS:
        try:
            decoded = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        # 解出的串若含路径分隔符异常或明显无效字符，继续试下一个编码
        if decoded and "\x00" not in decoded:
            return decoded
    return info.filename


def safe_target(dest_root, name):
    """阻止 zip slip：确保解压目标仍在 dest_root 之内。"""
    clean = name.replace("\\", "/").lstrip("/")
    target = os.path.normpath(os.path.join(dest_root, clean))
    root = os.path.normpath(dest_root)
    if not (target == root or target.startswith(root + os.sep)):
        return None
    return target


def main():
    ap = argparse.ArgumentParser(description="UTF-8 安全解压")
    ap.add_argument("zipfile")
    ap.add_argument("-d", "--dest", default=".")
    ap.add_argument("--list", action="store_true", help="只列出条目，不解压")
    ap.add_argument("--dry-run", action="store_true", help="预览解压路径，不写盘")
    args = ap.parse_args()

    if not os.path.isfile(args.zipfile):
        print(f"[错误] 找不到文件：{args.zipfile}")
        return 2

    dest_root = os.path.abspath(args.dest)
    total = 0
    skipped = 0

    with zipfile.ZipFile(args.zipfile) as zf:
        infos = zf.infolist()
        if args.list:
            for info in infos:
                print(f"{info.file_size:>12,}  {decode_name(info)}")
            print(f"\n共 {len(infos)} 个条目")
            return 0

        if not args.dry_run:
            os.makedirs(dest_root, exist_ok=True)

        for info in infos:
            name = decode_name(info)
            target = safe_target(dest_root, name)

            if target is None:
                print(f"[跳过] 路径越界：{name}")
                skipped += 1
                continue

            if info.is_dir():
                if not args.dry_run:
                    os.makedirs(target, exist_ok=True)
                continue

            if args.dry_run:
                print(f"[预览] {name}  ->  {target}")
                total += 1
                continue

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            total += 1

    verb = "预览" if args.dry_run else "解压"
    print(f"[完成] {verb} {total} 个文件 -> {dest_root}")
    if skipped:
        print(f"[注意] 跳过 {skipped} 个路径越界条目")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
