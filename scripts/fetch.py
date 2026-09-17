#!/usr/bin/env python3
"""稳健下载器 —— 本机 Windows 环境专用。

把反复踩过的坑固化下来：
  1. curl 必须 --ssl-no-revoke（否则 schannel 吊销检查失败，http_code=000）
  2. 必须带浏览器 UA（否则被 WAF 拦，返回 567）
  3. github.com/.../archive/...zip 自动改写成 codeload 直链（archive 链接会下到 90% 被掐断）
  4. 自动重试 + 断点续传

用法：
    python fetch.py <url> [-o 输出路径] [--retries 5] [--no-resume] [--timeout 20]
"""
import argparse
import os
import re
import subprocess
import sys

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# github.com/<owner>/<repo>/archive/refs/{heads|tags}/<ref>.zip  ->  codeload 直链
ARCHIVE_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/"
    r"archive/refs/(?P<kind>heads|tags)/(?P<ref>.+?)\.zip/?$"
)


def rewrite_github(url):
    """把会中途断流的 archive 链接改写成 codeload 直链。返回 (新url, 是否改写)。"""
    m = ARCHIVE_RE.match(url)
    if not m:
        return url, False
    new = (
        "https://codeload.github.com/"
        f"{m.group('owner')}/{m.group('repo')}/zip/refs/"
        f"{m.group('kind')}/{m.group('ref')}"
    )
    return new, True


def guess_output(url):
    """没给 -o 时从 URL 末段猜一个文件名。"""
    tail = url.rstrip("/").split("/")[-1].split("?")[0]
    return tail or "download.bin"


def build_cmd(url, out, retries, resume, timeout):
    cmd = [
        "curl", "--ssl-no-revoke", "-L",
        "-H", f"User-Agent: {BROWSER_UA}",
        "--connect-timeout", str(timeout),
        "--retry", str(retries), "--retry-all-errors",
        "--retry-delay", "3",
        "-w", "%{http_code} %{size_download}",
        "-o", out,
    ]
    if resume and os.path.exists(out) and os.path.getsize(out) > 0:
        cmd += ["-C", "-"]
    cmd.append(url)
    return cmd


def main():
    ap = argparse.ArgumentParser(description="稳健下载器（Windows 专用）")
    ap.add_argument("url")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    url, rewritten = rewrite_github(args.url)
    out = args.output or guess_output(url)

    if rewritten:
        print(f"[改写] archive -> codeload 直链")
    print(f"[下载] {url}")
    print(f"[保存] {os.path.abspath(out)}")

    cmd = build_cmd(url, out, args.retries, not args.no_resume, args.timeout)
    proc = subprocess.run(cmd, capture_output=True, text=True)

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    http_code, size = "?", "0"
    parts = stdout.split()
    if len(parts) >= 2:
        http_code, size = parts[-2], parts[-1]

    ok = proc.returncode == 0 and http_code.startswith("2") and os.path.exists(out)

    if ok:
        real = os.path.getsize(out)
        print(f"[完成] HTTP {http_code}  文件大小 {real:,} 字节")
        if real < 1024 and real > 0:
            print("[警告] 文件不足 1KB，可能拿到的是错误页而不是目标内容。")
        return 0

    print(f"[失败] curl 退出码 {proc.returncode}  HTTP {http_code}")
    if stderr:
        print(f"[stderr] {stderr[:800]}")
    if http_code == "000":
        print("[提示] http_code=000 通常是 TLS 吊销检查问题，确认 --ssl-no-revoke 已带上。")
    elif http_code == "567" or http_code.startswith("4") or http_code.startswith("5"):
        print("[提示] 可能被 WAF 拦截。换 UA 或先看返回体是不是拦截页。")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError:
        print("[错误] 找不到 curl。Windows 10+ 自带 curl.exe，或改用 Python urllib 方案。")
        sys.exit(2)
