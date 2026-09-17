# windows-fetch-and-reverse

**An agent skill for Windows that fixes the two most annoying classes of work: reliably fetching external resources, and reverse-engineering PyInstaller binaries.**

**一个 Windows 平台的 Agent 技能包：把「外部资源稳定取进来」和「PyInstaller 程序拆开」这两件反复踩坑的事，变成可以直接照做的操作指令。**

---

## English

### The problem

Running an AI coding agent on Windows means losing hours to a predictable set of traps:

| Symptom | Real cause |
|---|---|
| `curl` returns `http_code=000`, `CRYPT_E_NO_REVOCATION_CHECK` | schannel certificate revocation check fails |
| A site returns HTTP 567 or an interception page | default user agent blocked by WAF |
| `git clone` hangs at a few KB forever | git protocol unfriendly on this network |
| Extracted files have garbled CJK names | Git Bash `unzip` ignores the UTF-8 flag bit |
| `npm install` hangs on `fetch manifest` for 40 minutes | local HTTP proxy |
| You cannot unpack an `.exe` | you do not know which Python version packed it |

### What this skill gives you

Battle-tested rules plus three **dependency-free** Python scripts (stdlib only).
Every rule comes from a real debugging session — not from documentation.

### Contents

```
windows-fetch-and-reverse/
├── SKILL.md                     # routing table + six core rules
├── references/
│   ├── fetch-playbook.md        # download chain: TLS, WAF, codeload, extraction, mirrors
│   ├── reverse-playbook.md      # PyInstaller: cookie, CArchive TOC, PYZ, xdis
│   └── environment-quirks.md    # proxy / sandbox / encoding / tooling traps
└── scripts/
    ├── fetch.py                 # resilient downloader
    ├── safe_unzip.py            # UTF-8 safe extraction
    └── pe_probe.py              # PyInstaller probe
```

### Quick start

```bash
# 1. Probe before you unpack: is it PyInstaller? Which Python version?
python scripts/pe_probe.py target.exe

# 2. Download without getting blocked or cut off
python scripts/fetch.py \
  https://github.com/owner/repo/archive/refs/heads/main.zip -o repo.zip

# 3. Extract without corrupting CJK filenames
python scripts/safe_unzip.py repo.zip -d ./out
```

### What the scripts actually do

**`fetch.py`** — rewrites `github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip` into the
`codeload.github.com` direct link automatically (the `archive` endpoint is known to drop the
connection at roughly 90%), attaches a browser user agent, disables the revocation check,
and retries with resume support.

**`safe_unzip.py`** — decodes entry names properly. If the zip lacks the UTF-8 flag bit it
re-decodes through UTF-8 / GBK / Big5, and it refuses path-traversal entries.

**`pe_probe.py`** — reads the 24-byte PyInstaller cookie at the end of the file, reports the
packing Python version (which determines your disassembly toolchain), and lists the CArchive TOC.

### Verified

Every script is covered by a self-test that was actually executed, including one live download:

| Test | Result |
|---|---|
| CJK filename round-trip (3 nested paths) | pass |
| Non-PyInstaller file correctly rejected | pass |
| Synthetic PyInstaller archive parsed (`3.13`, TOC offset) | pass |
| Live download from `raw.githubusercontent.com` (3,053 bytes) | pass |

### Scope and disclaimer

This skill is intended for **legitimate** engineering work: analysing binaries you own or are
licensed to analyse, recovering your own build artefacts, and downloading resources you are
permitted to download.

It is **not** for circumventing paywalls, bypassing authentication, bulk-collecting personal
data, or any activity that violates applicable law or a service's terms.

### License

MIT

---

## 中文

### 它解决什么问题

在 Windows 上跑 AI 编码 Agent，时间会成批地丢在几个可预测的坑里：

| 现象 | 真因 |
|---|---|
| curl 返回 `http_code=000`、`CRYPT_E_NO_REVOCATION_CHECK` | schannel 证书吊销检查失败 |
| 站点返回 567 或拦截页 | 默认 UA 被 WAF 拦 |
| `git clone` 卡在几 KB 不动 | 本机网络对 git 协议不友好 |
| 解压后中文文件名乱码 | Git Bash 的 `unzip` 不认 UTF-8 标志位 |
| `npm install` 卡在 `fetch manifest` 四十分钟 | 本机 HTTP 代理 |
| 想拆 exe 却无从下手 | 不知道它是哪个 Python 版本打的包 |

### 它给你什么

经过实战验证的规则，加上三个**零依赖**（纯标准库）的 Python 脚本。
**每一条规则都来自真实排查会话，不是从文档里抄的。**

### 快速开始

```bash
# 1. 拆包之前先探：是不是 PyInstaller？哪个 Python 版本？
python scripts/pe_probe.py target.exe

# 2. 下载不再被拦、不再被掐断
python scripts/fetch.py \
  https://github.com/owner/repo/archive/refs/heads/main.zip -o repo.zip

# 3. 解压不再毁掉中文文件名
python scripts/safe_unzip.py repo.zip -d ./out
```

### 三个脚本到底做了什么

**`fetch.py`** —— 自动把 `github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip` 改写成
`codeload.github.com` 直链（`archive` 端点实测会在约 90% 处掐断连接），带上浏览器 UA、
关闭吊销检查，并支持重试与断点续传。

**`safe_unzip.py`** —— 正确解码条目名。若 zip 未打 UTF-8 标志位，会依次用 UTF-8 / GBK / Big5
重新解码；同时拒绝路径穿越条目。

**`pe_probe.py`** —— 读取文件尾部 24 字节的 PyInstaller cookie，报告打包用的 Python 版本
（它决定你后续的反汇编工具链），并列出 CArchive 的 TOC。

### 实测

每个脚本都配有**真正跑过**的自测，其中包含一次真实网络下载：

| 测试项 | 结果 |
|---|---|
| 中文文件名往返（3 个嵌套路径） | 通过 |
| 非 PyInstaller 文件正确判否 | 通过 |
| 合成 PyInstaller 包正确解析（`3.13`、TOC 偏移） | 通过 |
| 从 `raw.githubusercontent.com` 真实下载（3,053 字节） | 通过 |

### 适用范围与免责声明

本技能面向**正当**的工程用途：分析你拥有或获授权分析的二进制、恢复你自己的构建产物、
下载你有权下载的资源。

**不**用于绕过付费墙、绕过身份验证、批量收集个人数据，或任何违反适用法律与服务条款的行为。

### 许可

MIT
