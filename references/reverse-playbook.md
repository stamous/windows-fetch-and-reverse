# 逆向手册（reverse-playbook）

把 PyInstaller 打包的 exe 拆开，取出代码结构、常量与字符串。适用于 Python 程序逆向、行为审计、参数确认（如串口波特率）、以及「这程序到底干了什么」的排查。

## 0. 前置：先探针，别急着解包

```bash
python scripts/pe_probe.py app.exe
```

探针会报告：

- 是否为 PyInstaller 打包（尾部是否存在 `MEI\014\013\012\013\016` cookie）
- 打包所用的 **Python 版本**（决定后续反汇编工具链，跨版本读不了 pyc）
- CArchive 的 TOC 条目概览，是否含 PYZ

**先把 exe 复制到工作区再操作**，不要直接在桌面或下载目录里解包——输出目录会建在「当前工作目录」下，不是 exe 旁边。

```bash
cp /path/to/app.exe ./work/ && cd ./work
```

## 1. 省事路线（推荐先用这条）

```bash
# 装到隔离目录（走腾讯镜像，官方源会卡）
pip install pyinstxtractor-ng --target ./_rev -i https://mirrors.cloud.tencent.com/pypi/simple

# 一次性全解包（含 PYZ）
PYTHONPATH=./_rev python ./_rev/pyinstxtractor_ng.py app.exe
```

要点：

- `pyinstxtractor-ng` 会顺带装上 `xdis`，省去单独装。
- 日志里会**点名入口点脚本**，直接看日志即可定位主逻辑文件。
- 输出目录建在**当前工作目录**下，不是 exe 旁边。这是最常见的「解完了找不到东西」。

## 2. 精细路线：手动解 CArchive 与 PYZ

需要理解结构、或工具失效时使用。

### 2.1 定位 cookie

PyInstaller 2.0+ 把 24 字节 cookie 放在**文件末尾**：

```
magic[8] = b'MEI\x0c\x0b\x0a\x0b\x0e'
lengthofPackage[4]   # 大端
toc[4]               # TOC 偏移（相对 CArchive 起点），大端
tocLen[4]            # 大端
pyver[4]             # 打包所用 Python 版本，大端
```

```python
import struct
with open('app.exe', 'rb') as f:
    f.seek(-24, 2)
    magic = f.read(8)                                  # b'MEI\x0c\x0b\x0a\x0b\x0e'
    pkg_len, toc, toc_len, pyver = struct.unpack('!IIII', f.read(16))
```

### 2.2 读 CArchive TOC

CArchive 起点 = 文件末尾往前 `pkg_len` 字节。TOC 条目格式：

```
entryLen[4]  entryPos[4]  cmprsdDataSize[4]  uncmprsdDataSize[4]  cmprsFlag[1]  typeCmprsData[1]  name[entryLen]
```

其中 `typeCmprsData` 为 `z`（即 `122`）的条目就是 **PYZ**。

```python
import struct
with open('app.exe', 'rb') as f:
    f.seek(-pkg_len, 2)
    archive_start = f.tell()
    f.seek(archive_start + toc)
    for _ in range(toc_len // 18):
        entry = f.read(18)
        entry_len, entry_pos, csize, usize = struct.unpack('!IIII', entry[:16])
        flag, typ = entry[16], entry[17]
        name = f.read(entry_len).rstrip(b'\x00').decode('utf-8', 'replace')
        # typ == ord('z') 即 PYZ
```

### 2.3 PYZ 的 TOC 在 marshal 里

PYZ 内部的 TOC 不是明文，需要先解出位置：

```python
import marshal, zlib
# data 为解压后的 PYZ 内容
tocpos = marshal.loads(data[8:12])   # 前 8 字节是 magic
```

每个条目是 zlib 压缩 + marshal 序列化，解出后拼成标准 pyc：

```python
# 标准 pyc = magic(4) + 位标志(12) + blob
blob = zlib.decompress(entry_data)
pyc = magic + struct.pack('<III', 0, 0, 0) + blob
```

## 3. 从 pyc 提取信息（比完整反编译快得多）

```python
import xdis.load
code = xdis.load.load_module('module.pyc')
```

**注意：`load_module` 返回的是 8 元组，不是 7 个。** 遍历找带 `co_code` 属性的那个元素才是 code object：

```python
for item in xdis.load.load_module('module.pyc'):
    if hasattr(item, 'co_code'):
        co = item
        break
```

然后递归收割，比全量反编译快一个数量级：

```python
def harvest(co, strings, names):
    strings.extend(c for c in co.co_consts if isinstance(c, str))
    names.extend(co.co_names)
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            harvest(c, strings, names)
```

- `co_consts` —— 收字符串常量（含中文）
- `co_names` —— 收标识符（函数名、模块名、属性名）
- 只想捞字符串时，也可以直接对解压后的 blob 跑「UTF-8 可打印串」正则，中文同样能拿到。

## 4. 跨版本反汇编

**3.11 的 pyc，3.13 的解释器读不了。** 跨版本必须用 `xdis` 反汇编，不要试图用本机 Python 的 `dis`：

```bash
python -m xdis.bin.pydisasm module.pyc
```

读 dis 输出时，函数参数名和常量值都在 `Constants:` 与 `Varnames:` 段里，**直接读这两段**即可拿到如串口波特率、默认路径这类具体值，不必还原完整源码。

## 5. 注意事项

- **先 cp 到工作区再解**，且注意输出目录落在「当前工作目录」，不是 exe 旁边。
- **批量删除基本删不掉**：即使明确确认，`Remove-Item -Recurse -Force` 也会被静默拦截；PowerShell `Add-Type` 被禁（禁止运行时编译 .NET），所以走不了 `VisualBasic.FileIO` 回收站方案。超过阈值的目录**只能让用户自己在资源管理器里拖进回收站**。
- **不要基于乱码输出做判断**：Python 打印中文时若未设 `PYTHONIOENCODING=utf-8`，管道会渲染成乱码但文件完好。诊断前先强制 UTF-8 重读。
- 逆向仅用于自有程序、授权审计或学习研究。对第三方商业软件的解包可能涉及许可与法律风险，动手前先与用户确认授权来源。
