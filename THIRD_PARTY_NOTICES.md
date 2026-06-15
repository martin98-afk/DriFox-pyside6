# 第三方依赖许可证声明 (Third-Party Notices)

本项目使用并依赖于以下第三方开源组件。本文件汇总各组件的版权、许可证及必要的归属信息。
项目作者对各上游项目及其贡献者致以诚挚感谢。

---

## 1. 核心运行时依赖 (Runtime Dependencies)

| 组件 | 许可证 | 来源 | 备注 |
|------|--------|------|------|
| **PySide6** (≥6.8.0) | **LGPL 3.0** / GPL 2.0 / GPL 3.0 / 商业许可 | The Qt Company | Qt 6 官方 Python 绑定 (Qt for Python)，含 QtCore / QtGui / QtWidgets / QtWebEngine / QtNetwork 等模块 |
| **Qt 6 Framework** | **LGPL 3.0** / GPL 2.0 / GPL 3.0 / 商业许可 | The Qt Company | 由 PySide6 间接分发；完整许可证文本见 `LICENSE.LGPL-3.0` |
| **loguru** (≥0.7.0) | MIT | Delgan | Python 日志库 |
| **openai** (≥1.0.0) | Apache-2.0 | OpenAI | OpenAI API 官方 SDK |
| **httpx** (≥0.25.0) | BSD-3-Clause | Encode OSS | 异步 HTTP 客户端 |
| **html2text** (≥2020.1.16) | GPL-3.0 | Aaron Swartz 等 | HTML 转纯文本 |
| **beautifulsoup4** (≥4.12.0) | MIT | Leonard Richardson | HTML/XML 解析 |
| **PyYAML** (≥6.0) | MIT | Kirill Simonov | YAML 解析 |
| **fastapi** (≥0.100.0) | MIT | Sebastián Ramírez | Web 框架 (内置 HTTP 服务) |
| **uvicorn** (≥0.23.0) | BSD-3-Clause | Encode OSS | ASGI 服务器 |
| **psutil** | BSD-3-Clause | Giampaolo Rodola | 进程与系统监控 |
| **markdown** | BSD-3-Clause | David Worth 等 | Markdown 渲染 |
| **pygments** | BSD-2-Clause | Georg Brandl | 语法高亮 |
| **requests** | Apache-2.0 | Kenneth Reitz | 同步 HTTP 客户端 |
| **orjson** (≥3.8.0) | Apache-2.0 / MIT | ijl | 快速 JSON 库 |
| **pypinyin** | MIT | 闲耘 (mozillazg) | 汉字转拼音 |

## 2. 可选依赖 - Gateway 通讯平台 (Optional: `gateway` extra)

仅在安装 `[gateway]` 额外依赖时引入：

| 组件 | 许可证 | 来源 |
|------|--------|------|
| **dingtalk-stream** (≥0.20) | Apache-2.0 | 钉钉开放平台 |
| **python-telegram-bot** (≥20.0) | GPL-3.0 | Leandro Toledo |
| **discord.py** (≥2.0) | MIT | Rapptz |
| **slack-sdk** (≥3.0) | MIT | Slack Technologies |
| **lark-oapi** (≥1.0) | MIT | 飞书开放平台 |
| **aiohttp** (≥3.9.0) | Apache-2.0 | aio-libs |

## 3. 开发依赖 (Dev Dependencies)

仅在开发/打包场景下需要：

| 组件 | 许可证 | 来源 |
|------|--------|------|
| **pyinstaller** (≥6.16.0) | GPL-2.0 / 商业双许可 | PyInstaller Team |
| **pytest** (≥7.0.0) | MIT | Holger Krekel |
| **pytest-asyncio** (≥0.21.0) | Apache-2.0 | Tin Tvrtković |
| **black** (≥23.0.0) | MIT | Łukasz Langa |
| **ruff** (≥0.1.0) | MIT | Charlie Marsh (Astral) |
| **mypy** (≥1.0.0) | MIT | Jukka Lehtosalo |

---

## 4. LGPL 库合规要点 (LGPL Library Compliance Highlights)

本节针对作为本项目主要运行时依赖的 **PySide6 / Qt 6** (LGPL 3.0) 的合规要点做集中说明，
完整合规细节见 `LGPL_COMPLIANCE.md`。

### 4.1 Qt 6 第三方模块许可证差异

Qt 6 中部分子模块可能采用**非 LGPL** 许可证，常见如下：

| Qt 模块 | 实际采用的许可证 |
|---------|------------------|
| Qt Core / Gui / Widgets / Network / Qml / Quick | **LGPL 3.0** / GPL 2.0 / GPL 3.0 |
| Qt WebEngine | **LGPL 3.0** (含部分 BSD/Apache/MIT 组件) |
| Qt Charts / Qt Data Visualization | **GPL 3.0** (LGPL 不可用，需商业许可) |
| Qt 3D / Qt Bluetooth / Qt Multimedia | 视版本而定，可能为 LGPL / GPL / 商业 |

> ⚠️ 若在商业分发中使用了 **GPL-only** 模块（如 Qt Charts），需**购买 Qt 商业许可**或替换实现。
> 本项目**默认不依赖 Qt Charts / Qt Data Visualization** 等 GPL-only 模块。

### 4.2 LGPL 库源码获取方式

依据 LGPL 3.0 § 4(d)(0) 及 § 6 的要求，本项目**必须**为最终用户提供获取 LGPL 库
（PySide6 / Qt 6）源码的途径，方式包括：

1. **PySide6 (Python 包) 源码**: <https://code.qt.io/cgit/pyside/pyside-setup.git/>
2. **Qt 6 (C++ 主库) 源码**: <https://download.qt.io/official_releases/qt/>
3. **本项目仓库**: <https://github.com/martin98-afk/DriFox-pyside6>

### 4.3 应用重链接性 (Application Relinkability)

依据 LGPL 3.0 § 4(d)(1)：

- 本项目发布为 **wheel / PyInstaller 单文件** 时，仅作 *Combined Work* 形式静态链接 Qt。
- **用户可用以下方式替换 Qt 库**（重链接）：
  1. 从 PyPI 安装 `PySide6-Essentials` / `PySide6-Addons`，将动态库置于运行目录的 `PySide6/` 子目录；
  2. 或使用本项目源码自行 `python -m build` / `pyinstaller` 打包，并在打包命令中链接自定义 Qt 版本；
  3. 或在终端设置 `LD_LIBRARY_PATH` (Linux) / `DYLD_LIBRARY_PATH` (macOS) / `PATH` (Windows) 指向自定义 Qt 库目录。

---

## 5. 上游协议完整文本获取

| 协议 | 获取地址 |
|------|----------|
| LGPL 3.0 | 本仓库 `LICENSE.LGPL-3.0` (官方 FSF 完整英文文本) |
| GPL 2.0 | <https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt> |
| GPL 3.0 | <https://www.gnu.org/licenses/gpl-3.0.txt> |
| MIT | <https://opensource.org/licenses/MIT> |
| Apache-2.0 | <https://www.apache.org/licenses/LICENSE-2.0> |
| BSD-2-Clause / BSD-3-Clause | <https://opensource.org/licenses/BSD-2-Clause> / <https://opensource.org/licenses/BSD-3-Clause> |

---

## 6. 致谢 (Acknowledgements)

本项目站在以下巨人肩膀之上（按字母序）：

- **The Qt Company / Qt Project** — 跨平台 GUI 框架
- **Python Software Foundation** — Python 解释器
- **loguru / openai / httpx / fastapi** 等上百个开源项目及背后贡献者

如果您认为本文件的归属信息有遗漏或错误，请提交 Issue 或 PR。
