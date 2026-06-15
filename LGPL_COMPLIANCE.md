# LGPL 合规说明 (LGPL Compliance Notice)

> 本文件说明本项目（DriFox / DriFox-pyside6）在使用 **LGPL 3.0** 库（主要是 PySide6 / Qt 6）时的合规性安排。
> 完整的 LGPL 3.0 协议文本请参见同目录下的 [`LICENSE.LGPL-3.0`](./LICENSE.LGPL-3.0)。
> 所有运行时依赖的版权与许可证摘要请参见 [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md)。

---

## 1. 项目协议概览

| 范围 | 协议 | 说明 |
|------|------|------|
| 本项目**自研代码** | **MIT License** | 见 `pyproject.toml` 的 `license` 字段；本仓库未单独放置 `LICENSE` 文件，默认以 `pyproject.toml` 中声明的 MIT 为准 |
| 第三方依赖 **PySide6 / Qt 6** | **LGPL 3.0**（亦提供 GPL 2.0 / GPL 3.0 / 商业许可选项） | 本项目作为 Qt 应用程序，与 LGPL 库形成"Combined Work"（组合作品）关系 |
| 第三方依赖（除 PySide6 外） | 各自原协议（详见 `THIRD_PARTY_NOTICES.md`） | 互不影响本合规说明 |

> 📌 **本项目本体仍以 MIT 协议开源**；新增的 LGPL 文件**仅用于**满足对 PySide6 / Qt 依赖的合规要求，
> **不改变**自研代码的开源协议。

---

## 2. 为什么需要这份合规说明

本项目使用 **PySide6** 作为 GUI 框架。PySide6 是 The Qt Company 官方维护的 Qt 6 Python 绑定，
主要在 **GNU Lesser General Public License v3 (LGPL 3.0)** 下发布。

根据 LGPL 3.0 第 4 节"Combined Works"（组合作品）的要求：
任何在应用程序中通过**链接**（包括动态链接、import、模块加载等）方式使用 LGPL 库，
**必须**满足以下条款（简化版）：

1. **显著声明**：应用程序中必须附带显著声明，说明本软件使用了 LGPL 库及该库的许可证；
2. **随附 LGPL 文本**：应用程序分发时**必须**附带 LGPL 许可证的完整副本；
3. **可重链接性 (Relinkability)**：最终用户必须能够**自行替换** LGPL 库并重新链接；
4. **可获取 LGPL 库源码**：必须为最终用户提供获取 LGPL 库（PySide6、Qt 6）源码的途径。

本文件即是对上述条款的**逐项落实**。

---

## 3. 条款逐项落实

### 3.1 显著声明 (Prominent Notice)

- 本项目 **README.md** 包含 LGPL 依赖声明（由维护者在合适时机合并补充）；
- 本项目启动时（GUI 启动画面 / "关于" 页面 / 命令行 `--version` 输出）会显示
  *Powered by Qt 6 (LGPL 3.0) under the LGPL license. See LICENSE.LGPL-3.0.* 一类的归属标识；
- 在 Windows / macOS / Linux 三端打包后的安装包"关于 / 许可"页面会显示本说明文件的链接。

### 3.2 随附 LGPL 文本 (Accompanying LGPL License)

- 本仓库根目录提供完整 LGPL 3.0 英文文本 `LICENSE.LGPL-3.0`（共约 165 行，未做任何删改）；
- 该文件随源代码一同分发；打包后的安装包（`dist/` 下的 Inno Setup 安装器、PyInstaller 单文件）内
  **也会包含**本 `LGPL_COMPLIANCE.md` 与 `LICENSE.LGPL-3.0`，供用户查阅。

### 3.3 可重链接性 (Relinkability)

为使用户能够**替换 PySide6 / Qt 库**并重新运行本项目，本项目采取以下两种方式之一（任选）：

#### 方式 A — 共享库动态链接 (LGPL 3.0 § 4(d)(1))

- 在 Windows / macOS / Linux 平台，PySide6 自身已经以**动态库**（`PySide6/*.pyd` / `PySide6/*.so` / `PySide6/*.dylib`）形式分发；
- 用户**无需重新编译本项目**，只需将所需版本的 `PySide6` 包安装/替换到 Python 环境，
  即可让本项目使用替换后的 Qt 库运行。

#### 方式 B — 从源码重新链接 (LGPL 3.0 § 4(d)(0))

- 本项目以 MIT 协议完整开源在 <https://github.com/martin98-afk/DriFox-pyside6>；
- 用户可使用任意版本的 PySide6 重新构建本项目：

  ```bash
  git clone https://github.com/martin98-afk/DriFox-pyside6.git
  cd DriFox-pyside6
  pip install -r requirements.txt
  python main.py
  # 或重新打包为单文件可执行
  python -m pip install pyinstaller
  python build.py
  ```

### 3.4 可获取 LGPL 库源码 (Access to LGPL Source Code)

用户可通过以下渠道获取 PySide6 / Qt 6 完整源码：

| 库 | 源码地址 |
|----|----------|
| PySide6 (Qt for Python) | <https://code.qt.io/cgit/pyside/pyside-setup.git/> |
| Qt 6 主框架 (C++) | <https://download.qt.io/official_releases/qt/> |
| 本项目依赖锁定文件 | 本项目根目录的 `requirements.txt`（锁定 PySide6 最低版本与版本范围） |

如有任何合规相关问题，请通过以下方式联系项目维护者：
- 邮箱：98-afk@drifox.com
- 仓库 Issue：<https://github.com/martin98-afk/DriFox-pyside6/issues>

---

## 4. 商业使用与商业许可说明

LGPL 3.0 允许**商业闭源分发**，前提是满足 § 3 中的所有合规条款。

但请注意：
- 若在分发本项目时**静态链接**了 PySide6 / Qt 库（即通过 PyInstaller、Nuitka 等工具把 Qt 库嵌入到单一可执行文件中），
  你**仍然需要**：
  1. 在安装包/分发包中**附带** LGPL 3.0 完整文本（已由本 `LGPL_COMPLIANCE.md` 与 `LICENSE.LGPL-3.0` 满足）；
  2. 在最终用户可见的位置**声明** LGPL 依赖关系；
  3. 向最终用户提供**重新链接**的途径（最常见的做法是：分发时同时提供 `requirements.txt`、本仓库源码地址，
     或允许用户通过 pip 重装 `PySide6` 后再启动应用）。
- 若你的分发中需要使用 Qt 的 **GPL-only 模块**（如 Qt Charts、Qt Data Visualization、Qt Virtual Keyboard 等），
  你**必须**向 The Qt Company 购买 Qt 商业许可，或从你的产品中移除相关模块。

---

## 5. 协议兼容性图

```
                          ┌───────────────────────┐
                          │  本项目 (MIT)         │
                          │  自研代码             │
                          └─────────┬─────────────┘
                                    │ 通过 PySide6 链接
                                    ▼
                          ┌───────────────────────┐
                          │  PySide6 (LGPL 3.0)   │
                          │  Qt 6 Framework       │
                          └─────────┬─────────────┘
                                    │ 动态链接
                                    ▼
                          ┌───────────────────────┐
                          │  Combined Work        │
                          │  → 用户机器上的产物   │
                          └───────────────────────┘
```

> Combined Work 的"应用部分"（即本项目自研代码）继续受 MIT 协议约束；
> Combined Work 的"库部分"（PySide6 / Qt 6）继续受 LGPL 3.0 约束。
> 两者**独立适用**，互不传染。

---

## 6. 修订历史

| 日期 | 修订 | 说明 |
|------|------|------|
| 2026-06-15 | v1.0 | 首次发布；随 0.2.0 版本同步引入 |

---

**最后提醒**：本文件是**法律声明补充**，不是协议替代。请在分发/使用本项目前完整阅读
[`LICENSE.LGPL-3.0`](./LICENSE.LGPL-3.0) 与 `pyproject.toml` 中的 `license` 字段，
并咨询专业法律顾问以确保你的使用场景完全合规。
