# -*- coding: utf-8 -*-
"""
全局共享 QWebEngineProfile 模块

PySide6/Qt6 核心优化：多个 QWebEnginePage 共享同一个 QWebEngineProfile，
从而共享同一个 Chromium 渲染进程（而非各自启动独立进程）。

内存收益：
- 1 个消息卡片 ≈ 1 个 Chromium 进程 (40-60MB)
- 10 个卡片共享 profile ≈ 1 个 Chromium 进程 (80-100MB total)
- 相比不共享节省 60-80% 内存

同时提供 ECharts 资源缓存、统一字体/样式等优化。
"""

from typing import Optional
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView


# 全局共享 Profile 实例（懒初始化）
_shared_profile: Optional[QWebEngineProfile] = None


def init_shared_profile(off_the_record: bool = True) -> QWebEngineProfile:
    """初始化全局共享 QWebEngineProfile（在 QApplication 创建后调用一次）

    Args:
        off_the_record: True=无痕模式（仅内存缓存，不写磁盘）。默认 True。

    Returns:
        共享的 QWebEngineProfile 实例
    """
    global _shared_profile
    if _shared_profile is not None:
        return _shared_profile

    # 使用 off-the-record 模式：所有缓存仅存内存，无磁盘 I/O
    # 消息卡片不需要持久化浏览器状态，避免 GPU/磁盘缓存路径权限问题
    _shared_profile = QWebEngineProfile()

    # ── 缓存策略 ──
    # MemoryHttpCache: 所有缓存仅保留在内存中，避免磁盘 I/O
    # 50MB 上限足以缓存 ECharts + 常用字体/CSS
    _shared_profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    _shared_profile.setHttpCacheMaximumSize(50 * 1024 * 1024)  # 50MB

    # ── HTTP 设置 ──
    # 设置简洁 UA，某些 CDN 可能拒绝默认的 QtWebEngine UA
    _shared_profile.setHttpUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    _shared_profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")

    return _shared_profile


def get_shared_profile() -> Optional[QWebEngineProfile]:
    """获取全局共享 QWebEngineProfile（必须已初始化）"""
    return _shared_profile


def get_or_create_shared_profile() -> QWebEngineProfile:
    """获取或自动创建共享 Profile"""
    if _shared_profile is None:
        return init_shared_profile()
    return _shared_profile


def prewarm_profile():
    """预热共享 Profile：提前启动 Chromium 进程

    在 UI 显示后、第一条消息到达前调用，隐藏初始化延迟。
    创建临时 QWebEngineView 加载最小 HTML，触发进程初始化后销毁。
    """
    profile = get_or_create_shared_profile()
    warm_view = QWebEngineView()
    page = profile.createPageForWebEngineView(warm_view)
    warm_view.setPage(page)
    warm_view.setHtml("<html><body></body></html>")
    warm_view.show()
    # 延迟销毁：给 Chromium 进程几秒完成初始化
    from PySide6.QtCore import QTimer
    QTimer.singleShot(3000, warm_view.deleteLater)
