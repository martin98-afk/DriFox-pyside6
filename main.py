# -*- coding: utf-8 -*-
"""
LLM Chatter 主入口
以独立弹窗模式启动，无需 FluentWindow 框架
"""
import os
import sys
import warnings

from PySide6.QtGui import QFont

warnings.filterwarnings("ignore")
os.environ["PYTHONIOENCODING"] = "utf-8"

# ========== 内存诊断开关 ==========
# 设为 False 可禁用所有 [MEM] 诊断日志和 mem_diag.log 文件
# 关闭后 Worker 内也不再执行内存快照和自适应 GC 日志
MEM_DIAG_ENABLED = False

# 同步给 Worker（Worker 读取 MEM_DIAG 环境变量）
if MEM_DIAG_ENABLED:
    os.environ["MEM_DIAG"] = "1"
else:
    os.environ.pop("MEM_DIAG", None)  # 不设任何值，Worker 默认启用

# ========== tracemalloc 深度追踪 ==========
# 当 MEM_DIAG_ENABLED=True 且需要定位具体内存分配热点时，设为 True
# 会增加运行时开销，仅在排查时开启
# 可通过命令行 MEM_TRACE=1 python main.py 临时覆盖
MEM_TRACE_ENABLED = False
if MEM_TRACE_ENABLED:
    os.environ["MEM_TRACE"] = "1"
else:
    os.environ.pop("MEM_TRACE", None)

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    """启动 LLM Chatter"""
    import platform
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from loguru import logger
    from app.utils import icons_rc

    # ========== 必须在创建 QApplication 之前设置 Qt 属性 ==========
    # 这些设置必须在任何 Qt 模块导入之前或 QApplication 创建之前完成

    # DPI 缩放设置
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # OpenGL 共享上下文设置
    # AA_DontCreateNativeWidgetSiblings：macOS 上启用会导致 Cocoa 插件问题，跳过
    # AA_ShareOpenGLContexts：macOS 也必须启用，否则创建第二个 QWebEngineView
    #   时 Chromium GPU 进程会触发 SIGTRAP（trace trap）崩溃
    if platform.system() != "Darwin":
        QApplication.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    # ── Chromium flags 优化（Qt6 WebEngine 基于 Chromium 99+）──
    #
    # 说明：Qt5 WebEngine 基于 Chromium 77，性能/兼容性受限。
    #       Qt6 WebEngine 基于 Chromium 99+，支持更多现代特性。
    #
    # 平台兼容：macOS 仍需 in-process-gpu 防止 SIGTRAP；
    #           Windows/Linux 可用独立 GPU 进程，安全性更好。
    #
    # 内存控制：num-raster-threads=2 限制光栅化线程数，
    #           对多卡片场景降低总内存峰值。
    import os as _os
    _flags = _os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")

    # ── 平台特定 ──
    if platform.system() == "Darwin":
        if "--in-process-gpu" not in _flags:
            _flags += " --in-process-gpu"

    # ── 通用优化 ──
    # 注：PyQt5 时期为绕过 cdn.jsdelivr.net 旧 TLS 兼容问题加了
    #     --ignore-certificate-errors，PySide6/Qt6 (Chromium 99+)
    #     TLS 协议栈已经完整，移除该 flag 以恢复正常的证书校验（更安全）。
    #     如果生产环境发现 CDN 加载异常，可临时加回。

    # 禁用不必要的 Chromium 功能模块，减少内存/CPU
    # (PySide6 WebEngine 中这些功能永远不会被使用)
    for flag in (
        "--disable-features=TranslateUI",       # 禁用翻译（Chromium 内置翻译栏）
        "--disable-sync",                        # 禁用同步服务
        "--disable-background-networking",       # 禁用后台网络请求
        "--disable-component-update",            # 禁用组件更新检查
        "--enable-features=CanvasOopRasterization",  # 离屏 Canvas 加速（ECharts）
    ):
        if flag not in _flags:
            _flags += f" {flag}"

    # 限制光栅化线程数（默认等于 CPU 核心数，多卡片时浪费）
    if "--num-raster-threads" not in _flags:
        _flags += " --num-raster-threads=2"

    _os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _flags.strip()

    # ========== 导入可能触发 WebEngine 的模块（在 QApplication 创建之前）==========
    # 提前导入，确保在 app 创建之前触发
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401

    from app.utils.utils import get_app_data_dir
    # 迁移旧版本数据（打包版从安装目录迁到用户 home 目录）
    from app.utils.utils import migrate_app_data_if_needed
    migrate_app_data_if_needed()

    # 设置日志 (使用统一路径获取方法，DMG 只读时也需要可写)
    log_dir = get_app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "llm_chatter.log",
        rotation="10 MB",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )

    # 单独的内存诊断日志文件（仅含 [MEM] / [MEM-LEAK] 标签的日志）
    # 用于排查工具迭代中的内存泄漏，与业务日志分离便于查看
    # 由 main.py 顶部的 MEM_DIAG_ENABLED 控制总开关
    if MEM_DIAG_ENABLED:
        logger.add(
            log_dir / "mem_diag.log",
            rotation="10 MB",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            filter=lambda r: "[MEM]" in r["message"],
        )

    # 创建应用
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Drifox")
    app.setApplicationDisplayName("Drifox")

    # PySide6/Qt6 优化：初始化全局共享 QWebEngineProfile
    # 必须在 QApplication 创建后、任何 WebEngineView 创建前调用
    from app.utils.web_profile import init_shared_profile
    init_shared_profile()

    # 禁用 Qt 的 qFatal 默认行为（abort），改为记录 ERROR 日志
    # PyQt5 默认：信号槽中 Python 异常 → pyqt5_err_print() → qFatal() → abort()
    # 自定义处理器将 qFatal 转换为日志，防止整个进程崩溃
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType
    from loguru import logger as _logger

    def _qt_message_handler(msg_type, msg_context, msg_text):
        if msg_type == QtMsgType.QtFatalMsg:
            _logger.error(f"[QtFatal] {msg_text}")
            # 不 abort()，仅记录日志后返回，让进程继续运行
            # 注意：某些 PyQt5 版本中 pyqt5_err_print() 直接在 C++ 层调用 abort()
            # 此处理器无法阻止那一类 abort，需要配合信号槽外层 try-catch
        elif msg_type == QtMsgType.QtCriticalMsg:
            _logger.error(f"[QtCritical] {msg_text}")

    qInstallMessageHandler(_qt_message_handler)

    # 全局 Python 异常钩子（兜底）
    import traceback as _traceback
    def _pyqt_exception_hook(exc_type, exc_val, exc_tb):
        _logger.error(f"[UnhandledException] {exc_type.__name__}: {exc_val}")
        _logger.error("".join(_traceback.format_exception(exc_type, exc_val, exc_tb)))
    sys.excepthook = _pyqt_exception_hook

    # sys.unraisablehook：处理 Python 对象析构时抛出的不可捕获异常
    # 防止 GC 收集 SIP 包装器时对象已释放导致的内存错误
    def _unraisable_hook(unraisable):
        msg = getattr(unraisable.exc_value, 'args', (str(unraisable.exc_value),))
        err_msg = msg[0] if msg else str(unraisable.exc_value)
        _logger.error(f"[UnraisableException] {unraisable.exc_type.__name__}: {err_msg}")
        if unraisable.object:
            _logger.error(f"  Object: {unraisable.object!r}")
        _logger.error(f"  Err: {unraisable.err_msg}")
    sys.unraisablehook = _unraisable_hook
    
    # 禁用默认退出行为（让最后一个窗口隐藏到托盘而不是退出）
    app.setQuitOnLastWindowClosed(False)

    # ========== 单实例检查 ==========
    # 在 QApplication 创建之后立即检查，
    # 避免在已运行的情况下重复创建窗口
    from app.core.single_instance import SingleInstanceGuard
    _guard = SingleInstanceGuard("Drifox")
    if not _guard.try_lock():
        # 已有实例在运行 → 通知其显示窗口，然后本实例退出
        _guard.request_show_window()
        _guard.cleanup()
        return

    # 设置主题
    from app.utils.fluent_shim import Theme, setTheme
    setTheme(Theme.DARK)
    # 获取全局字体配置
    try:
        from app.utils.config import Settings
        font_family = Settings.get_instance().llm_font_family.value
    except Exception:
        try:
            font_family = Settings.get_instance().canvas_font_selected.value
        except Exception:
            font_family = "Segoe UI"

    # 启动时同步开机自启注册表状态
    try:
        from app.utils.startup_manager import sync_auto_start_from_config
        sync_auto_start_from_config()
    except Exception:
        logger.exception("[AutoStart] main.py 中调用 sync_auto_start_from_config 失败")

    try:
        from app.utils.design_tokens import scale_font_size
        tooltip_font_size = scale_font_size(12)
    except Exception:
        tooltip_font_size = 12

    app.setStyleSheet(f"""
            QToolTip {{
                color: #ffffff;
                background-color: rgba(30, 30, 32, 240);
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 2px 2px;
                font-size: {tooltip_font_size}px;
                font-family: '{font_family}';
            }}
        """)
    # 创建并显示窗口 - 直接使用 ToolPopupDialog
    logger.info("LLM Chatter 启动中...")

    from app.main_widget import OpenAIChatToolWindow
    from PySide6.QtWidgets import QWidget

    # 创建模拟的 homepage
    class FakePage(QWidget):
        def __init__(self):
            super().__init__()
            from app.utils.config import Settings
            self.cfg = Settings.get_instance()
            font = QFont()
            font.setFamilies([self.cfg.llm_font_family.value])
            from PySide6.QtWidgets import QApplication
            QApplication.setFont(font)

        def isActiveWindow(self):
            return True

        @property
        def workflow_name(self):
            return "standalone_llm_chatter"

        @property
        def global_variables_changed(self):
            class FakeSignal:
                def connect(self, *args, **kwargs):
                    pass

            return FakeSignal()

        def setUpdatesEnabled(self, enabled):
            pass

        def update(self):
            pass

        def show_splitter(self):
            pass

        def hide_splitter(self):
            pass

    fake_page = FakePage()
    chat_window = OpenAIChatToolWindow(fake_page)

    # 延迟创建 ToolPopupDialog 和初始化 TrayManager
    # 等 chat_window 的 __init__ 完成后再创建弹窗，避免窗口渲染阻塞主线程
    from PySide6.QtCore import QTimer

    def _activate_window(window):
        """激活窗口：显示 + 置前 + 还原（从最小化/隐藏恢复）"""
        window.show()
        window.activateWindow()
        window.raise_()
        if window.isMinimized():
            window.showNormal()

    def _show_popup():
        # ToolPopupDialog 构造（包含 QSettings 读取、布局构建）
        # 注：TrayManager 已由 ToolPopupDialog 延迟初始化，不再在此处创建
        from app.tool_popup import ToolPopupDialog
        popup = ToolPopupDialog(chat_window, None)
        popup.setWindowTitle("Drifox")

        # 跳过历史会话恢复
        chat_window._skip_restore_history = True

        # 连接单实例信号：当其他实例启动时，激活本窗口
        _guard.show_requested.connect(lambda: _activate_window(popup))

        # 在 show() 之前恢复几何位置，避免窗口先出现在默认位置再跳转导致闪烁
        popup._restore_geometry()
        popup._geometry_restored = True

        popup.show()
        logger.info("LLM Chatter 启动成功")

    # 应用退出时清理单实例资源（共享内存 + IPC 服务器）
    app.aboutToQuit.connect(_guard.cleanup)
    # 标记数据库正常关闭，下次启动跳过完整性检查
    from app.core.store.session_store import SessionStore
    app.aboutToQuit.connect(SessionStore.mark_clean_shutdown)

    # 等 chat_window.__init__ 完成后再创建弹窗
    QTimer.singleShot(0, _show_popup)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()