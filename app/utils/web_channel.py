# -*- coding: utf-8 -*-
"""
QWebChannel 桥接模块 - PySide6/Qt6 类型安全通信

替代 console.log('pywebview_height:N') 字符串解析方案。

原理：
    JS (qwebchannel.js) ↔ QWebChannel ↔ Python QObject
    方法调用：JS → QWebChannel → Python slot（直接传类型化参数）
    信号推送：Python signal → QWebChannel → JS callback（类型化事件）

当前覆盖：
    - heightReported(int): JS 上报 WebEngine 高度（最高频事件）
    - contentReady(): JS 通知骨架加载完成（一次性）

未覆盖（仍用 console.log 桥接）：
    - code action / context / tool_diff / subagent_log / save_file
      （低频事件，已有 console.log 桥接正常工作）
"""

from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot


class WebChannelBridge(QObject):
    """暴露给 JS 的 QWebChannel 桥接对象

    使用方式：
        bridge = WebChannelBridge(self)
        channel = QWebChannel(page)
        channel.registerObject("bridge", bridge)
        page.setWebChannel(channel)
    """

    # JS → Python（直接调用）
    # 高度上报：JS 主动调 bridge.reportHeight(h)
    # 内容就绪：JS 主动调 bridge.notifyReady()
    heightReported = Signal(int)
    contentReady = Signal()
    # 图表导出：JS 右键图表时触发，参数 (type, id, clientX, clientY)
    chartExportRequested = Signal(str, str, int, int)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

    @Slot(int)
    def reportHeight(self, h: int):
        """JS 主动调：上报当前内容高度"""
        self.heightReported.emit(h)

    @Slot()
    def notifyReady(self):
        """JS 主动调：通知内容已就绪"""
        self.contentReady.emit()

    @Slot(str, str, int, int)
    def requestChartExport(self, chart_type: str, chart_id: str, client_x: int, client_y: int):
        """JS 右键图表时调用：请求导出图表 (echarts/mermaid) 为 SVG"""
        self.chartExportRequested.emit(chart_type, chart_id, client_x, client_y)

    # ── 图表导出数据回传 ──
    # Python 端通过 runJavaScript 让 JS 提取 SVG 数据，
    # JS 完成后通过 QWebChannel 调用本 slot 回传结果。
    # 这避免了 page.runJavaScript(callback) 在嵌套事件循环中不触发的问题。
    svgDataReady = Signal(str)

    @Slot(str)
    def receiveSvgData(self, data: str):
        """JS 完成 SVG 提取后调用：回传 SVG 数据字符串"""
        self.svgDataReady.emit(data)


# QWebChannel 的 JS shim URL（Qt 内置 qrc 资源）
# Qt 6.7+ 也支持通过 page.setWebChannel() 自动注入
QWEBCHANNEL_JS_URL = "qrc:///qtwebchannel/qwebchannel.js"
