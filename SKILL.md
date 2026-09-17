---
name: windows-fetch-and-reverse
description: 本机 Windows 环境下"把外部资源稳定取进来"与"把 PyInstaller 打包的程序拆开"的实战技能包。当任务涉及从 GitHub 或任意站点下载文件与整包、curl 报 CRYPT_E_NO_REVOCATION_CHECK 或 http_code=000、被 WAF 拦截返回 567、git clone 卡死不动、解压后中文文件名乱码、npm 或 pip 安装假死、需要逆向 PyInstaller 打包的 exe、提取 pyc 或 PYZ、跨 Python 版本反汇编、收割程序内字符串时使用。Triggers - download github repo zip, curl ssl-no-revoke, WAF 567, unzip garbled CJK filename, npm registry hang, PyInstaller unpack, pyinstxtractor, xdis disassemble, pyc cross-version.
display_name: Windows 取件与逆向实战包
display_name_en: Windows Fetch & Reverse Toolkit
description_zh: 把「外部资源稳定取进来」与「PyInstaller 程序拆开」变成可直接照做的操作指令，附三个零依赖脚本。
description_en: Reliably fetch external resources and reverse-engineer PyInstaller binaries on Windows, with three dependency-free scripts.
category: developer-tools
version: 1.0.0
author: stamous
agent_created: true
---

# Windows 取件与逆向实战包

## 用途

覆盖两件高频、且每次都要重新踩一遍的事：

1. **取件（fetch）** —— 在这台 Windows 机器上，把外部资源（GitHub 仓库、raw 文件、release 资产、任意 HTTPS 站点）稳定下载到本地，并正确解压。
2. **逆向（reverse）** —— 把 PyInstaller 打包的 exe 拆开，取出代码结构、常量与字符串，必要时跨 Python 版本反汇编。

两者共同的前提是**本机环境的若干硬约束**（代理、沙箱、编码）。因此 `environment-quirks.md` 是前两者的地基，任何一步卡住都先回去查它。

## 路由：先判断任务属于哪一类

| 用户意图 | 走哪本手册 |
|---|---|
| 下载 / 拉取 / 获取 GitHub 仓库或文件；下载被拦、中断、拿不到内容；解压乱码 | `references/fetch-playbook.md` |
| 逆向 / 拆包 / 提取 exe 里的代码或字符串；反编译 PyInstaller 程序 | `references/reverse-playbook.md` |
| 命令莫名卡死、报权限或沙箱错误、中文乱码、删除失败、PowerShell 无输出 | `references/environment-quirks.md` |

判断不明确时，先读 `environment-quirks.md`，再读对应手册。

## 核心铁律

不读手册也必须遵守，这六条覆盖了绝大部分翻车场景：

1. **curl 访问 HTTPS 必须加 `--ssl-no-revoke`**。否则 schannel 报 `CRYPT_E_NO_REVOCATION_CHECK (0x80092012)`，http_code=000，拿不到任何内容。
2. **curl 默认 UA 会被 WAF 拦**。返回 567 或拦截页时，先加浏览器 UA 重试，再考虑代理或 DNS。
3. **不要用 `git clone` 拉 GitHub 仓库**。实测卡在几 KB 不动。改用 codeload 直链或 raw 直取。
4. **不要用 Git Bash 的 `unzip`**。它不认 zip 的 UTF-8 标志位，中文文件名会解成乱码，依赖文件名的程序会直接崩。改用 Python `zipfile`。
5. **npm / pip 走官方源会假死**。npm 显式加 `--registry=https://registry.npmmirror.com`；pip 走 `-i https://mirrors.cloud.tencent.com/pypi/simple`。
6. **批量删除不要指望命令行**。超过阈值的目录即使明确确认也会被静默拦截，只能让用户自己在资源管理器里拖进回收站。

## 随附脚本

三个脚本把最容易写错的逻辑固化了。**优先直接调用，不要临时重写**：

| 脚本 | 作用 | 典型调用 |
|---|---|---|
| `scripts/fetch.py` | 稳健下载器。自动把 `github.com/<o>/<r>/archive/...zip` 改写成 codeload 直链，带浏览器 UA、吊销检查绕过、重试与断点续传 | `python scripts/fetch.py <url> -o out.zip` |
| `scripts/safe_unzip.py` | UTF-8 安全解压。正确识别 zip 的 UTF-8 标志位，中文文件名不乱码 | `python scripts/safe_unzip.py x.zip -d ./out` |
| `scripts/pe_probe.py` | exe 探针。判断是否 PyInstaller 打包、定位尾部 cookie、报告打包所用 Python 版本 | `python scripts/pe_probe.py app.exe` |

三个脚本**仅依赖 Python 标准库**，Python 3.10+ 均可直接运行，无需安装任何第三方包。

## 工作流

```
用户要拿一个外部资源
  └─ fetch-playbook.md
       ├─ 判断目标类型（单文件 / 整包 / release 资产）
       ├─ scripts/fetch.py 下载
       └─ scripts/safe_unzip.py 解压

用户要拆一个 exe
  └─ reverse-playbook.md
       ├─ scripts/pe_probe.py 先确认是 PyInstaller、拿到 Python 版本
       ├─ 省事路线：pyinstxtractor-ng 一次性全解包
       └─ 精细路线：xdis 提取 code object / 反汇编

任何一步卡住
  └─ environment-quirks.md
```
