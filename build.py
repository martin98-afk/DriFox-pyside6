# -*- coding: utf-8 -*-
"""
Build a Windows/macOS onedir package for Drifox.

Based on PeekAgent's build_win.py approach:
  - Use --exclude-module to skip unnecessary PySide6 modules at build time
  - Post-build cleanup for WebEngine debug files & unnecessary translations
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

# ── 项目名称 ──────────────────────────────────────────────────────
APP_NAME = "Drifox"
ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
APP_DIR = DIST_DIR / APP_NAME

# ── 不需要打包的 PySide6 模块（按需排除） ──────────────────────────
QT_MODULE_EXCLUDES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtHttpServer",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebView",
    # 科学计算 / 大数据（本项目无需）
    "matplotlib",
    "scipy",
    "pandas",
    "numpy",
]

# ── 保留的翻译文件后缀 ──────────────────────────────────────────────
TRANSLATION_KEEP_SUFFIXES = ("_zh_CN.qm", "_en.qm")

# ── 保留的 WebEngine 区域文件 ──────────────────────────────────────
WEBENGINE_LOCALE_KEEP_FILES = {"zh-CN.pak", "en-US.pak"}


# ── 数据文件 ────────────────────────────────────────────────────────
def _data_args() -> list[str]:
    """收集 --add-data 参数"""
    entries: list[tuple[Path, str]] = [
        # 插件目录
        (ROOT_DIR / "plugins", "plugins"),
    ]
    args: list[str] = []
    for src, dest in entries:
        args.append(f"--add-data={src}{os.pathsep}{dest}")
    return args


# ── 构建参数 ────────────────────────────────────────────────────────
def _build_args() -> list[str]:
    args: list[str] = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        APP_NAME,
        # 隐式导入：PySide6 模块中动态加载的
        "--hidden-import=PySide6.QtWebEngineCore",
        "--hidden-import=PySide6.QtWebEngineWidgets",
        "--hidden-import=PySide6.QtNetwork",
        # 排除不需要的 Qt 模块
    ]
    for module_name in QT_MODULE_EXCLUDES:
        args.append(f"--exclude-module={module_name}")

    # 图标
    icon_path = ROOT_DIR / "icons" / "drifox.ico"
    if icon_path.exists():
        args.extend(["--icon", str(icon_path)])

    # 数据文件
    args.extend(_data_args())

    # 入口脚本
    args.append(str(ROOT_DIR / "main.py"))
    return args


# ── 清理 ────────────────────────────────────────────────────────────
def _clean() -> None:
    """清理之前构建的产物"""
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(APP_DIR, ignore_errors=True)


# ── 版本提取 ──────────────────────────────────────────────────────
def _extract_version() -> str:
    """从 CHANGELOG.md 首行提取版本号"""
    changelog = ROOT_DIR / "CHANGELOG.md"
    if not changelog.exists():
        return "development"
    first_line = changelog.read_text(encoding="utf-8").splitlines()[0].strip()
    if not first_line:
        return "development"
    ver = re.sub(r"^\s*#+\s*", "", first_line).strip()
    ver = re.sub(r"^\[(.*)\]$", r"\1", ver).strip()
    return ver or "development"


def _write_version_file() -> str:
    """写入 version.txt 供运行时读取"""
    version = _extract_version()
    (ROOT_DIR / "version.txt").write_text(version + "\n", encoding="utf-8")
    return version


# ── 打包后精简 ──────────────────────────────────────────────────────
def _clean_packaged_files(app_dir: Path) -> None:
    """
    移除打包后不必要的文件：
      1. WebEngine debug 资源
      2. 大部分翻译文件（仅保留 zh_CN / en）
    """
    removed_files: list[tuple[Path, int]] = []

    def _remove(path: Path) -> None:
        if not path.is_file():
            return
        size = path.stat().st_size
        path.unlink()
        removed_files.append((path, size))

    # PySide6 资源目录
    pyside_dir = app_dir / "_internal" / "PySide6"
    if not pyside_dir.is_dir():
        return

    # 1) WebEngine debug 资源
    resources_dir = pyside_dir / "resources"
    if resources_dir.is_dir():
        debug_names = [
            "qtwebengine_devtools_resources.debug.pak",
            "qtwebengine_resources.debug.pak",
            "qtwebengine_resources_100p.debug.pak",
            "qtwebengine_resources_200p.debug.pak",
        ]
        for name in debug_names:
            _remove(resources_dir / name)

        debug_snapshot = resources_dir / "v8_context_snapshot.debug.bin"
        release_snapshot = resources_dir / "v8_context_snapshot.bin"
        if release_snapshot.is_file():
            _remove(debug_snapshot)

    # 2) 翻译文件精简
    translations_dir = pyside_dir / "translations"
    if translations_dir.is_dir():
        for qm_file in translations_dir.glob("*.qm"):
            if qm_file.name.endswith(TRANSLATION_KEEP_SUFFIXES):
                continue
            _remove(qm_file)

        webengine_locales = translations_dir / "qtwebengine_locales"
        if webengine_locales.is_dir():
            for locale_file in webengine_locales.glob("*"):
                if locale_file.name in WEBENGINE_LOCALE_KEEP_FILES:
                    continue
                _remove(locale_file)

    # 3) 清理 __pycache__
    for root, dirs, _ in os.walk(app_dir):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)

    if removed_files:
        total = sum(size for _, size in removed_files)
        print(f"\n精简: 移除 {len(removed_files)} 个文件，节省 {total / (1024 * 1024):.1f} MiB")
        for path, size in removed_files:
            print(f"  - {path.relative_to(app_dir)} ({size / (1024 * 1024):.1f} MiB)")
    else:
        print("\n精简: 无需移除额外文件")


# ── 入口 ────────────────────────────────────────────────────────────
def main() -> int:
    print(f"Drifox 构建开始 — 目标: {sys.platform}")
    print(f"版本: {_extract_version()}")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    _clean()

    # 写入版本文件（可选，供运行时验证）
    _write_version_file()

    # 执行 PyInstaller 打包
    print("\n正在执行 PyInstaller 打包...")
    PyInstaller.__main__.run(_build_args())

    # 验证打包目录存在
    if not APP_DIR.is_dir():
        print(f"\n❌ 打包失败: {APP_DIR} 不存在")
        return 1

    # 后置精简
    print("\n正在执行打包后精简...")
    _clean_packaged_files(APP_DIR)

    print(f"\n✅ 打包完成: {APP_DIR}")
    print(f"   大小: {_dir_size_mib(APP_DIR):.1f} MiB")
    return 0


def _dir_size_mib(path: Path) -> float:
    """递归计算目录大小 (MiB)"""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total / (1024 * 1024)


if __name__ == "__main__":
    raise SystemExit(main())
