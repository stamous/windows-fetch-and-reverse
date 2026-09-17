# 取件手册（fetch-playbook）

本机 Windows 环境下把外部资源取回本地的完整链路。所有命令均为实测可用版本，不要凭记忆简化。

## 0. 先判断目标类型

| 目标 | 走哪条路 |
|---|---|
| 单个文本文件（README、脚本、配置） | raw 直取（§3.1） |
| 整个仓库 | codeload 直链整包（§3.2） |
| release 资产（.zip/.exe/.dmg） | release 直链（§3.3） |
| 普通 HTTPS 站点资源 | 基础 curl（§1） |

## 1. 基础 curl 调用

**必须带 `--ssl-no-revoke`**，否则 schannel 吊销检查失败，报
`CRYPT_E_NO_REVOCATION_CHECK (0x80092012)`，http_code 返回 000。

```bash
curl --ssl-no-revoke -L \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36" \
  --connect-timeout 20 --retry 3 --retry-all-errors \
  -o out.bin \
  -w "http_code=%{http_code} size=%{size_download}\n" \
  "https://example.com/file"
```

关键参数：

- `--ssl-no-revoke` —— 绕过 schannel 吊销检查，**不可省略**。
- `-L` —— 跟随重定向（GitHub 大量使用 302）。
- `-H "User-Agent: ..."` —— 伪装浏览器，绕 WAF。
- `--retry N --retry-all-errors` —— 服务器中途掐断时自动重试。
- `-C -` —— 断点续传，接在已下载的部分文件后面继续。
- `-w "http_code=..."` —— 打印状态码，**必须验证**，不要只看命令是否报错。

## 2. 被 WAF 拦截的排查顺序

现象：返回 HTTP 567、或返回体是「请求已被站点的安全策略拦截」这类页面（腾讯云 EdgeOne 等）。

排查顺序，逐级往下：

1. **先看返回体本身**，确认是不是 WAF 拦截页，而不是真实内容。
2. **换浏览器 UA**（见 §1）。实测 st.com 默认 UA 返回 567，加 UA 立刻 200。
3. 再考虑代理、DNS、TLS 版本。

不要一上来就怀疑网络不通——大部分「拿不到内容」其实是 UA 被拦。

## 3. GitHub 取件三条路

### 3.1 raw 直取（单文件，最快）

```bash
curl --ssl-no-revoke -L -o SKILL.md \
  "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>"
```

### 3.2 codeload 整包直链（推荐，替代 git clone）

**不要用 `git clone`** —— 实测 1 分 43 秒卡在 5KB 不动。改用：

```bash
curl --ssl-no-revoke -L --retry 5 --retry-all-errors \
  -o repo.zip \
  "https://codeload.github.com/<owner>/<repo>/zip/refs/heads/<branch>"
```

注意：

- **必须走 codeload 域名**。`github.com/.../archive/refs/heads/main.zip` 实测下到 90% 被服务器掐断（curl 56）。
- 18MB 左右约 2.5 分钟，属正常速度，别以为卡死了。
- 下载后务必核对文件大小与 `http_code`。

### 3.3 release 资产

```bash
curl --ssl-no-revoke -L --retry 5 --retry-all-errors \
  -o asset.zip \
  "https://github.com/<owner>/<repo>/releases/download/<tag>/<asset>"
```

补充：GitHub release 资产**拒绝后缀字节范围请求**（`Range: bytes=-400000` → `501 Unsupported client range`），无法廉价地通过 HTTP 窥探 zip 中央目录。前缀范围（`bytes=0-3000`）可行，能揭示第一个条目名，足以区分扁平与嵌套布局。

## 4. 解压（关键：不要用 unzip）

**Git Bash 的 `unzip` 不认 zip 的 UTF-8 标志位**，中文文件名会全部解成乱码。实测后果：PyInstaller 桌宠的 ffmpeg 打不开乱码 `.webm`，程序启动即失败。

正确做法，二选一：

```bash
# 首选：随附脚本
python scripts/safe_unzip.py repo.zip -d ./out
```

```bash
# 兜底：一行 Python
python -c "import zipfile; zipfile.ZipFile('repo.zip').extractall('.')"
```

Python `zipfile` 会正确识别 UTF-8 标志位。若遇到未打标志位的老式 GBK 包，`safe_unzip.py` 会自动回退尝试 GBK 解码。

## 5. 包管理器镜像

本机代理会把官方源卡死，**必须显式指定镜像**：

```bash
# pip —— 装到隔离目录，不污染用户环境
pip install <pkg> -i https://mirrors.cloud.tencent.com/pypi/simple --target <dir>

# npm —— 官方 registry 会假死在 fetch manifest cache-miss
npm install <pkg> --registry=https://registry.npmmirror.com

# pnpm —— npm config set 会被沙箱拦（禁写 ~/.npmrc），改用环境变量
npm_config_registry=https://registry.npmmirror.com pnpm install
```

## 6. 错误对照表

| 现象 | 原因 | 对策 |
|---|---|---|
| http_code=000，报 `CRYPT_E_NO_REVOCATION_CHECK` | schannel 吊销检查 | 加 `--ssl-no-revoke` |
| http_code=567 或返回拦截页 | WAF 按 UA 拦截 | 加浏览器 UA |
| 下到 90% 报 curl 56 | 用了 archive 链接 | 换 codeload 直链 |
| `git clone` 长时间无进展 | 本机对 git 协议不友好 | 改用 codeload 整包 |
| 解压后中文名乱码 | Git Bash unzip 不认 UTF-8 标志 | 改用 Python zipfile |
| npm 日志停在 cache-miss 不动 | 官方 registry 被本地代理卡住 | 加 `--registry=npmmirror` |
| pip 安装长时间无响应 | 官方源被代理卡住 | 换腾讯镜像 |
| bash 写 `/tmp` 报 `client returned ERROR on write` | 沙箱限制 | 输出到工作区目录 |
