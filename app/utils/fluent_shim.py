"""
QFluentWidgets → PySide6 原生组件兼容层（过渡）

临时兼容层让整个代码库在 PySide6 下可运行。
所有 qfluentwidgets 组件被替换为 PySide6 原生实现。
**目标：逐个文件替换后最终移除本模块。**
"""
from PySide6.QtCore import Qt, QSize, QObject, QEvent, QEasingCurve, QVariantAnimation, QRectF, QRect, QPropertyAnimation, Property, QPointF, QPoint, Signal as Signal
from PySide6.QtGui import QIcon, QColor, QFont, QPainter, QPixmap, QAction, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QHBoxLayout, QVBoxLayout,
    QComboBox, QPlainTextEdit, QTextEdit, QListWidget, QSpinBox, QCheckBox,
    QDialog, QMessageBox, QScrollArea, QTabBar, QSizePolicy,
    QStackedWidget, QApplication, QSlider, QLineEdit,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
)
from enum import Enum
from loguru import logger

# 注册 Qt 资源系统（编译自 icons/icons.qrc）
import app.utils.icons_rc  # noqa: F401


# ============ 基础组件 ============

def _load_icon_from_fs(name):
    """从 icons/ 目录直接加载（不依赖编译资源，发布环境可移除）"""
    import os
    icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "icons")
    for candidate in (f"{name}.svg", f"{name.lower()}.svg", f"{name.capitalize()}.svg"):
        path = os.path.join(icons_dir, candidate)
        if os.path.exists(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon
    return QIcon()


class FluentIcon:
    """FluentIcon 替代：使用内置 QIcon

    图标来自 icons/ 目录，编译入 icons_rc.py，通过 :/icons/ 加载。
    支持中英文文件名自动映射。
    """
    @staticmethod
    def _find_icon(name):
        """从本地资源系统查找图标（不区分大小写，支持中文别名）

        查找顺序：资源系统(:/icons/) → icons/ 目录文件(文件系统回退) → 中文别名 → PNG 回退
        """
        # 中文文件名 → 英文概念映射（icons/ 目录中部分 SVG 为中文名）
        _CN_ALIAS = {
            "delete": "删除",
            "copy": "复制",
            "font": "字体",
            "error": "惊叹号",
            "zip": "归档",
            "terminal": "工具",
            "image": "成功",
            "pause": "停止",
            "history": "历史对话",
            "return": "撤销",
            "more": "更多",
            "new": "新建",
            "sync": "同步",
            "setting": "配置管理",
        }
        # Qt 资源系统是大小写敏感的，逐一尝试
        candidates = [name, name.lower(), name.capitalize()]
        for c in candidates:
            icon = QIcon(f":/icons/{c}.svg")
            if not icon.isNull():
                return icon
        # 尝试中文别名
        alias = _CN_ALIAS.get(name.lower())
        if alias:
            icon = QIcon(f":/icons/{alias}.svg")
            if not icon.isNull():
                return icon
            icon = QIcon(f":/icons/{alias.lower()}.svg")
            if not icon.isNull():
                return icon
        # 文件系统回退：icons/ 目录（开发环境下新图标未重编译资源时兜底）
        for c in candidates:
            icon = _load_icon_from_fs(c)
            if not icon.isNull():
                return icon
        # PNG 回退
        icon = QIcon(f":/icons/{name.lower()}.png")
        if not icon.isNull():
            return icon
        return QIcon()

    @staticmethod
    def _load_from_fs(name):
        """从 icons/ 目录直接加载（不依赖编译资源，发布环境可移除）"""
        import os
        icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "icons")
        for candidate in (f"{name}.svg", f"{name.lower()}.svg", f"{name.capitalize()}.svg"):
            path = os.path.join(icons_dir, candidate)
            if os.path.exists(path):
                icon = QIcon(path)
                if not icon.isNull():
                    return icon
        return QIcon()

    # 常用图标（按使用频率排列）
    SETTING = _find_icon("setting")
    ADD = _find_icon("add")
    CLOSE = _find_icon("close")
    DELETE = _find_icon("delete")       # → 删除.svg
    EDIT = _find_icon("edit")            # → Edit.svg
    COPY = _find_icon("copy")            # → 复制.svg
    INFO = _find_icon("info")
    WARNING = _find_icon("warning")
    ERROR = _find_icon("error")          # → 惊叹号.svg
    FOLDER = _find_icon("folder")
    SYNC = _find_icon("sync")
    FONT = _find_icon("font")            # → 字体.svg
    SAVE = _find_icon("save")            # → Save.svg
    SEND = _find_icon("send")
    CODE = _find_icon("code")
    DOCUMENT = _find_icon("document")    # → Document.svg
    COMMAND_PROMPT = _find_icon("terminal")  # → 工具.svg
    IMAGE_EXPORT = _find_icon("image")       # → 成功.svg
    VIDEO = _find_icon("video")
    MUSIC = _find_icon("music")
    ZIP_FOLDER = _find_icon("zip")           # → 归档.svg
    PAUSE = _find_icon("pause")
    HELP = _find_icon("help")
    MENU = _find_icon("menu")
    APPLICATION = _find_icon("app")
    # ── P0 移植缺口图标（Fluent System Icons 20px regular）──
    LINK = _find_icon("Link")               # 链接
    MESSAGE = _find_icon("Message")         # 消息（信封）
    SHARE = _find_icon("Share")             # 分享
    HISTORY = _find_icon("history")         # 历史（→ 历史对话.svg 兜底）
    BOOK = _find_icon("Book")               # 书
    HEART = _find_icon("Heart")             # 心
    ZOOM = _find_icon("Zoom")               # 放大镜
    CHAT = _find_icon("Chat")               # 聊天气泡
    ALIGNMENT = _find_icon("Alignment")     # 文本对齐
    SHOPPING_CART = _find_icon("ShoppingCart")  # 购物车
    RETURN = _find_icon("return")           # 返回/撤销（→ 撤销.svg 兜底）
    BROOM = _find_icon("Broom")             # 清扫

    @staticmethod
    def icon():
        return QIcon()


FIF = FluentIcon  # 兼容 from app.utils.fluent_shim import FluentIcon as FIF


class InfoBar(QFrame):
    """简化版通知条"""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

    def __init__(self, icon=None, title="", content="", orient=Qt.Horizontal,
                 isClosable=True, position="bottom", duration=5000, parent=None):
        super().__init__(parent)
        self._duration = duration
        self._timer = None
        self.widgetLayout = QHBoxLayout(self)
        self.widgetLayout.setContentsMargins(12, 8, 12, 8)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("font-weight: bold;")
            self.widgetLayout.addWidget(title_lbl)
        if content:
            content_lbl = QLabel(content)
            self.widgetLayout.addWidget(content_lbl)
        self.widgetLayout.addStretch()

        if isClosable:
            close_btn = QPushButton("×")
            close_btn.setFixedSize(20, 20)
            close_btn.setStyleSheet("border: none; font-size: 14px;")
            close_btn.clicked.connect(self.close)
            self.widgetLayout.addWidget(close_btn)

        self.setStyleSheet("""
            InfoBar {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
        """)

        if duration > 0:
            from PySide6.QtCore import QTimer
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.close)
            self._timer.start(duration)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            parent_rect = self.parent().rect()
            self.adjustSize()
            self.move(
                (parent_rect.width() - self.width()) // 2,
                parent_rect.height() - self.height() - 30
            )

    @staticmethod
    def error(title, content, **kwargs):
        kwargs.setdefault('position', "bottom")
        kwargs.setdefault('duration', 5000)
        notif = InfoBar(icon=InfoBar.ERROR, title=title, content=content, **kwargs)
        notif.show()
        return notif

    @staticmethod
    def success(title, content, **kwargs):
        kwargs.setdefault('position', "bottom")
        kwargs.setdefault('duration', 5000)
        notif = InfoBar(icon=InfoBar.SUCCESS, title=title, content=content, **kwargs)
        notif.show()
        return notif

    @staticmethod
    def warning(title, content, **kwargs):
        kwargs.setdefault('position', "bottom")
        kwargs.setdefault('duration', 5000)
        notif = InfoBar(icon=InfoBar.WARNING, title=title, content=content, **kwargs)
        notif.show()
        return notif

    @staticmethod
    def info(title, content, **kwargs):
        kwargs.setdefault('position', "bottom")
        kwargs.setdefault('duration', 5000)
        notif = InfoBar(icon=InfoBar.INFO, title=title, content=content, **kwargs)
        notif.show()
        return notif


class InfoBarPosition:
    BOTTOM = "bottom"
    TOP = "top"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    NONE = "none"


class InfoBarIcon:
    INFORMATION = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class InfoLevel(Enum):
    """角标等级"""
    INFOAMTION = 'Info'
    SUCCESS = 'Success'
    ATTENTION = 'Attension'
    WARNING = "Warning"
    ERROR = "Error"


class InfoBadgePosition(Enum):
    """角标相对目标控件的位置（P0 移植缺口：main_widget 用 LEFT）"""
    TOP_RIGHT = 0
    BOTTOM_RIGHT = 1
    RIGHT = 2
    TOP_LEFT = 3
    BOTTOM_LEFT = 4
    LEFT = 5
    NAVIGATION_ITEM = 6


class InfoBadgeManager(QObject):
    """角标位置管理器 — 监听目标控件 move/resize 自动跟随"""

    managers = {}

    def __init__(self, target, badge):
        super().__init__()
        self.target = target
        self.badge = badge
        self.target.installEventFilter(self)

    def eventFilter(self, obj, e):
        if obj is self.target:
            if e.type() in (QEvent.Type.Resize, QEvent.Type.Move):
                self.badge.move(self.position())
        return super().eventFilter(obj, e)

    @classmethod
    def register(cls, name):
        def wrapper(Manager):
            if name not in cls.managers:
                cls.managers[name] = Manager
            return Manager
        return wrapper

    @classmethod
    def make(cls, position, target, badge):
        if position not in cls.managers:
            raise ValueError(f'`{position}` is an invalid animation type.')
        return cls.managers[position](target, badge)

    def position(self):
        return QPoint()


@InfoBadgeManager.register(InfoBadgePosition.TOP_RIGHT)
class _TopRightInfoBadgeManager(InfoBadgeManager):
    def position(self):
        pos = self.target.geometry().topRight()
        return QPoint(pos.x() - self.badge.width() // 2, pos.y() - self.badge.height() // 2)


@InfoBadgeManager.register(InfoBadgePosition.RIGHT)
class _RightInfoBadgeManager(InfoBadgeManager):
    def position(self):
        x = self.target.geometry().right() - self.badge.width() // 2
        y = self.target.geometry().center().y() - self.badge.height() // 2
        return QPoint(x, y)


@InfoBadgeManager.register(InfoBadgePosition.BOTTOM_RIGHT)
class _BottomRightInfoBadgeManager(InfoBadgeManager):
    def position(self):
        pos = self.target.geometry().bottomRight()
        return QPoint(pos.x() - self.badge.width() // 2, pos.y() - self.badge.height() // 2)


@InfoBadgeManager.register(InfoBadgePosition.TOP_LEFT)
class _TopLeftInfoBadgeManager(InfoBadgeManager):
    def position(self):
        return QPoint(self.target.x() - self.badge.width() // 2, self.target.y() - self.badge.height() // 2)


@InfoBadgeManager.register(InfoBadgePosition.BOTTOM_LEFT)
class _BottomLeftInfoBadgeManager(InfoBadgeManager):
    def position(self):
        pos = self.target.geometry().bottomLeft()
        return QPoint(pos.x() - self.badge.width() // 2, pos.y() - self.badge.height() // 2)


@InfoBadgeManager.register(InfoBadgePosition.LEFT)
class _LeftInfoBadgeManager(InfoBadgeManager):
    def position(self):
        x = self.target.x() - self.badge.width() // 2
        y = self.target.geometry().center().y() - self.badge.height() // 2
        return QPoint(x, y)


class InfoBadge(QLabel):
    """信息角标（P0 移植缺口：main_widget:2901 InfoBadge.attension）

    圆形圆角角标，支持 InfoBadge.attension(num, parent=..., target=..., position=...) 用法。
    构造签名兼容 qfluentwidgets：
        InfoBadge(parent, level)
        InfoBadge(text, parent, level)
        InfoBadge(num, parent, level)
    """
    def __init__(self, text="", parent=None, level=InfoLevel.ATTENTION):
        super().__init__(parent=parent)
        self.level = InfoLevel.INFOAMTION
        self.manager = None
        self.lightBackgroundColor = None
        self.darkBackgroundColor = None
        self.setLevel(level)
        font = self.font()
        font.setPointSize(9)
        self.setFont(font)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        if isinstance(text, str):
            self.setText(text)
        else:
            self.setNum(text)

    def setLevel(self, level):
        self.level = level
        self.setProperty('level', level.value)
        self.update()

    def setCustomBackgroundColor(self, light, dark):
        self.lightBackgroundColor = QColor(light)
        self.darkBackgroundColor = QColor(dark)
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._backgroundColor())
        r = self.height() / 2
        painter.drawRoundedRect(self.rect(), r, r)
        super().paintEvent(e)

    def _backgroundColor(self):
        isDark = isDarkTheme()
        if self.lightBackgroundColor:
            return self.darkBackgroundColor if isDark else self.lightBackgroundColor
        if self.level == InfoLevel.INFOAMTION:
            return QColor(157, 157, 157) if isDark else QColor(138, 138, 138)
        if self.level == InfoLevel.SUCCESS:
            return QColor(108, 203, 95) if isDark else QColor(15, 123, 15)
        if self.level == InfoLevel.ATTENTION:
            return QColor(0, 120, 212)  # 强调色（仿 themeColor 默认蓝）
        if self.level == InfoLevel.WARNING:
            return QColor(255, 244, 206) if isDark else QColor(157, 93, 0)
        return QColor(255, 153, 164) if isDark else QColor(196, 43, 28)

    @classmethod
    def make(cls, text, parent=None, level=InfoLevel.INFOAMTION, target=None,
             position=InfoBadgePosition.TOP_RIGHT):
        w = cls(text, parent, level)
        w.adjustSize()
        if target:
            w.manager = InfoBadgeManager.make(position, target, w)
            w.move(w.manager.position())
        return w

    @classmethod
    def info(cls, text, parent=None, target=None, position=InfoBadgePosition.TOP_RIGHT):
        return cls.make(text, parent, InfoLevel.INFOAMTION, target, position)

    @classmethod
    def success(cls, text, parent=None, target=None, position=InfoBadgePosition.TOP_RIGHT):
        return cls.make(text, parent, InfoLevel.SUCCESS, target, position)

    @classmethod
    def attension(cls, text, parent=None, target=None, position=InfoBadgePosition.TOP_RIGHT):
        """注意角标（qfluentwidgets 官方拼写为 attension，非 attention）"""
        return cls.make(text, parent, InfoLevel.ATTENTION, target, position)

    @classmethod
    def warning(cls, text, parent=None, target=None, position=InfoBadgePosition.TOP_RIGHT):
        return cls.make(text, parent, InfoLevel.WARNING, target, position)

    @classmethod
    def error(cls, text, parent=None, target=None, position=InfoBadgePosition.TOP_RIGHT):
        return cls.make(text, parent, InfoLevel.ERROR, target, position)

    @classmethod
    def custom(cls, text, light, dark, parent=None, target=None,
               position=InfoBadgePosition.TOP_RIGHT):
        w = cls.make(text, parent, target=target, position=position)
        w.setCustomBackgroundColor(light, dark)
        return w


class PrimaryPushButton(QPushButton):
    """主操作按钮 - 蓝色主题"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)


class PushButton(QPushButton):
    """普通按钮（半透明背景）"""
    def __init__(self, text="", parent=None, icon=None):
        super().__init__(text, parent)
        if isinstance(icon, FluentIcon):
            self.setIcon(icon)
        elif isinstance(icon, QIcon):
            self.setIcon(icon)
        self.setStyleSheet("""
            QPushButton {
                background: rgba(128, 128, 128, 0.12);
                color: palette(buttonText);
                border: 1px solid rgba(128, 128, 128, 0.2);
                border-radius: 6px;
                padding: 5px 16px;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.22);
                border-color: palette(highlight);
            }
            QPushButton:pressed {
                background-color: rgba(128, 128, 128, 0.32);
            }
            QPushButton:disabled {
                color: palette(mid);
            }
        """)


class TransparentPushButton(PushButton):
    """透明按钮 — 去边框透明版（P0 移植缺口：tab_panel 用）

    兼容 qfluentwidgets PushButton 的三种构造签名：
        TransparentPushButton(parent)
        TransparentPushButton(text, parent, icon)
        TransparentPushButton(icon, text, parent)
    """
    def __init__(self, text="", parent=None, icon=None):
        # 兼容 (icon, text, parent) 签名：icon 可能是 QIcon / FluentIcon 成员(QIcon)
        if isinstance(text, (QIcon, FluentIcon)) and not isinstance(text, str):
            icon, text, parent = text, parent, icon
        super().__init__(text, parent, icon)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: palette(buttonText);
                border-radius: 4px;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.15);
            }
            QPushButton:pressed {
                background-color: rgba(128, 128, 128, 0.28);
            }
            QPushButton:disabled {
                color: palette(mid);
            }
        """)


class TransparentToolButton(QPushButton):
    """透明工具按钮"""
    def __init__(self, icon=None, parent=None):
        # 兼容：第一个参数是 parent widget 而非 QIcon
        if isinstance(icon, QWidget) and parent is None:
            parent = icon
            icon = None
        super().__init__(parent)
        if isinstance(icon, QIcon):
            self.setIcon(icon)
        self.setAutoDefault(False)  # 防止 QDialog 按 Enter 时误触发
        self.setFixedSize(32, 32)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.15);
            }
        """)


class IconWidget(QLabel):
    """图标控件"""
    def __init__(self, icon=None, parent=None):
        # 兼容：第一个参数是 parent widget 而非 QIcon
        if isinstance(icon, QWidget) and parent is None:
            parent = icon
            icon = None
        super().__init__(parent)
        self.setFixedSize(16, 16)
        if isinstance(icon, QIcon) and not icon.isNull():
            self.setIcon(icon)

    def setIcon(self, icon):
        """设置图标"""
        if isinstance(icon, QIcon) and not icon.isNull():
            self.setPixmap(icon.pixmap(16, 16))
        elif hasattr(icon, 'icon') and callable(icon.icon):
            # 兼容 FluentIcon 风格的 icon 对象
            qicon = icon.icon()
            if isinstance(qicon, QIcon) and not qicon.isNull():
                self.setPixmap(qicon.pixmap(16, 16))


class ComboItemDelegate(QStyledItemDelegate):
    """下拉项自定义委托 — 显式绘制 hover/selected 视觉效果

    解决问题：Qt Fusion style 在 QAbstractItemView 应用 stylesheet 后，
    不再渲染 popup 中 ::item:hover 和 ::item:selected（已知 Qt 限制）。
    通过自定义委托显式绘制，绕过此限制，得到稳定可靠的视觉反馈。

    三态渲染逻辑（完全独立，互不依赖）：

    | 状态   | 背景                | 左侧标记条   | 文字色             | 触发       |
    |--------|---------------------|--------------|--------------------|------------|
    | 正常   | 透明                | 无           | TEXT_PRIMARY       | -          |
    | Hover  | 白色 14% 圆角矩形   | 无           | TEXT_PRIMARY       | 鼠标悬停   |
    | Selected | accent 18% 圆角矩形 | accent 实色 3px | accent (强调)   | 选中/键盘   |

    ⚠ 关键：selected 判定使用 combo.currentIndex()，而非 Qt 的 State_Selected。
       Qt 的 QComboBox 在 popup 模式下会把"鼠标悬停的项"也置上 State_Selected
       （hover = 预览选中），直接用 State_Selected 会导致标记条跟着光标跑。

    附加功能：
    - 支持 icon 渲染（位于文字前）
    - 字体取自 option.font（兼容 QFontComboBox 字体预览）
    - 颜色实时从 Colors 读取（主题热切换即时生效）
    """
    BG_RADIUS = 5      # 背景圆角半径
    SEL_BAR_WIDTH = 3  # 选中态左侧标记条宽度

    def __init__(self, combo=None, parent=None):
        """
        Args:
            combo: QComboBox 引用，用于访问 currentIndex() 判定"实际选中"。
                   传 None 则退回到 Qt.State_Selected（旧行为，不可靠）。
            parent: QStyledItemDelegate 父对象（通常是 view）
        """
        super().__init__(parent)
        self._combo = combo

    def _is_actually_selected(self, index) -> bool:
        """判定 index 是否对应 combo 的实际 currentIndex()（不跟 hover 走）

        仅当 index 的 model 与 combo 的 model 一致时才用 currentIndex 判定。
        例如：combo 的 view 用本判定；completer popup（独立 model）用 Qt state。
        """
        if self._combo is not None and index.model() is self._combo.model():
            return index.row() == self._combo.currentIndex()
        return bool(index.data(Qt.ItemDataRole.UserRole + 100)  # 保留扩展位
                    or False)

    def paint(self, painter, option, index):
        from app.utils.design_tokens import Colors
        Colors.refresh()

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # 应用 item 字体（用于 QFontComboBox 字体预览）
        painter.setFont(opt.font)

        # 关键：用 combo.currentIndex() 判定实际选中，不用 Qt 的 State_Selected
        if self._combo is not None and index.model() is self._combo.model():
            is_selected = (index.row() == self._combo.currentIndex())
        else:
            # 兜底：completer popup 等独立 model 的场景
            is_selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        is_enabled = bool(opt.state & QStyle.StateFlag.State_Enabled)

        rect = opt.rect
        accent = QColor(Colors.TEXT_ACCENT)

        # 1. 背景层
        if is_selected:
            # 选中态：accent 18% 背景（与 hover 的白色叠加颜色源不同，明显区分）
            bg = QColor(accent)
            bg.setAlphaF(0.18)
            painter.setBrush(bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, self.BG_RADIUS, self.BG_RADIUS)

            # 左侧 3px 实色标记条 — 固定的"选中"标识（不随 hover 改变）
            painter.fillRect(
                QRect(rect.left(), rect.top(), self.SEL_BAR_WIDTH, rect.height()),
                accent,
            )
            text_color = accent  # 选中文字用主题色强化
        elif is_hover:
            # 悬浮态：白色 ~14% 圆角叠加（瞬时反馈）
            painter.setBrush(QColor(255, 255, 255, 36))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, self.BG_RADIUS, self.BG_RADIUS)
            text_color = QColor(Colors.TEXT_PRIMARY) if is_enabled else QColor(Colors.TEXT_MUTED)
        else:
            text_color = QColor(Colors.TEXT_PRIMARY) if is_enabled else QColor(Colors.TEXT_MUTED)

        # 2. 图标层（位于文字前）
        text_x = rect.left() + 12  # 默认左 padding（与 stylesheet `padding: 8px 12px` 对齐）
        if not opt.icon.isNull():
            icon_size = opt.decorationSize
            icon_y = rect.top() + max(0, (rect.height() - icon_size.height()) // 2)
            icon_rect = QRect(rect.left() + 8, icon_y, icon_size.width(), icon_size.height())
            opt.icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
            text_x = icon_rect.right() + 6  # 图标右侧 6px 间距

        # 3. 文字层
        painter.setPen(text_color)
        text_rect = QRect(text_x, rect.top(), rect.right() - text_x - 8, rect.height())
        fm = painter.fontMetrics()
        elided = fm.elidedText(opt.text, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

        painter.restore()

    def sizeHint(self, option, index):
        """确保 item 高度不小于 28px（与 stylesheet `::item { min-height: 28px }` 对齐）"""
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height(), 28))


class ComboBox(QComboBox):
    """组合框 — 暗色精工工业风统一样式

    修复原生 QComboBox 问题：
    1. 弹出时锚定当前选中项 → showPopup 后 scrollToTop
    2. 空间不足时向上弹出 → 强制从控件下方展开
    3. view 样式每次 popup 时刷新 → 防止被系统样式覆盖
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_style()
        # 限制下拉可见项数（避免 20+ 项的下拉撑满屏幕）。
        # ⚠ 放在 __init__ 而非 _apply_style()，否则每次主题刷新都会
        # 把外部设置的 maxVisibleItems 重置为 8。
        self.setMaxVisibleItems(8)
        # 注册主题重载回调 → 重新应用样式以反映新主题色
        # （否则 stylesheet 在 __init__ 构建后永远不变，背景色停在旧主题）
        self._theme_reload_cb = None
        try:
            from app.utils.theme_manager import theme_manager
            self._theme_reload_cb = self._refresh_theme_style
            theme_manager.on_reload(self._theme_reload_cb)
        except Exception:
            pass

    def minimumSizeHint(self):
        """重写最小尺寸提示：不再基于最长下拉项，防止窄布局溢出

        QComboBox 默认的 minimumSizeHint 以最宽项的像素宽度为准，
        当搭配"标签+组合框+按钮"的横向布局时，长项文本会撑住组合框
        的最小宽度，导致右侧按钮被挤出可视区域。

        这里改为仅基于当前文本计算最小宽度，让布局系统可在空间不足时
        正常收缩组合框。
        """
        hint = super().minimumSizeHint()
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.currentText())
        # 保留 64px 给下拉按钮+内边距余量
        hint.setWidth(max(text_w + 64, 80))
        return hint

    def _apply_style(self):
        from app.utils.design_tokens import ComboBoxStyles
        self.setStyleSheet(ComboBoxStyles.dark_combo())
        # 自定义委托显式绘制 hover/selected（Fusion 限制：popup 中 stylesheet
        # 的 ::item:hover 不可靠，必须用委托）。传入 self 让委托能用 currentIndex()
        # 区分"实际选中"与"hover 预览"，防止标记条跟着光标跑。
        self.view().setItemDelegate(ComboItemDelegate(combo=self, parent=self.view()))

    def _refresh_theme_style(self):
        """主题切换时立即刷新样式（不等下次 popup）

        同步刷新：
        1. combo 自身的 stylesheet（边框/背景/箭头）
        2. view 的 stylesheet（popup 容器背景）
        3. view 的 palette（选中色）
        4. 强制 unpolish + polish + update → 解决"popup 更新了但 frame 颜色没变"的问题
        """
        try:
            from app.utils.design_tokens import Colors
            Colors.refresh()
            self._apply_style()
            self._apply_popup_style()  # 同步更新 view 样式（直接调用，不需要 QTimer）
            # 关键：setStyleSheet() 不会自动 unpolish 已缓存的 style，
            # 导致 frame 背景仍显示旧主题色。unpolish + polish 强制 Qt 重算样式。
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        except Exception:
            pass

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        # 注销主题回调，避免野指针
        if self._theme_reload_cb is not None:
            try:
                from app.utils.theme_manager import theme_manager
                theme_manager.remove_reload_callback(self._theme_reload_cb)
            except Exception:
                pass
            self._theme_reload_cb = None
        super().destroy(destroyWindow, destroySubWindows)

    def wheelEvent(self, event):
        """禁用滚轮切换 — 避免鼠标悬停时滚动误触改变值"""
        event.ignore()

    def showPopup(self):
        super().showPopup()
        # Qt6 关键：popup view 是独立顶层窗口，combo 的 stylesheet 无法穿透。
        # 必须在 showPopup 后延迟设 view 的样式 + palette。
        # 使用 0ms QTimer 推迟到事件循环下一帧（此时 view 已完全就绪）。
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_popup_style)
        v = self.view()
        v.scrollToTop()
        self._constrain_popup_height(v)
        popup = v.parentWidget()
        if popup and popup is not self:
            pt = self.mapToGlobal(self.rect().bottomLeft())
            popup.move(popup.x(), pt.y())
            # 约束：下拉框不超出屏幕可视区域（右边界）
            self._constrain_popup_horizontally(popup)

    def _constrain_popup_horizontally(self, popup):
        """将 popup 的水平位置约束在屏幕可用区域内，防止右侧溢出屏幕"""
        try:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.screenAt(popup.geometry().center()) or QGuiApplication.primaryScreen()
            if not screen:
                return
            screen_rect = screen.availableGeometry()
            pr = popup.geometry()
            # 超出右边界 → 左移
            if pr.right() > screen_rect.right():
                popup.move(screen_rect.right() - pr.width(), pr.y())
            # 超出左边界 → 右移
            if pr.left() < screen_rect.left():
                popup.move(screen_rect.left(), pr.y())
        except Exception:
            pass

    def _constrain_popup_height(self, view):
        """手动约束下拉 popup 容器的高度

        Qt6 某些 style（含 Fusion）下 setMaxVisibleItems 可能被
        QComboBoxPrivateContainer 内部 resize 覆盖，导致超大列表撑满屏幕。
        这里直接设置 popup 容器的 fixedHeight 作为兜底。
        """
        try:
            max_items = self.maxVisibleItems()
            count = self.count()
            if count <= max_items:
                return
            # sizeHintForRow(0) 可估算单行高度（含 stylesheet padding/min-height）
            if count > 0:
                row_h = view.sizeHintForRow(0)
                if row_h <= 0:
                    row_h = 36  # 兜底：28px min-height + 8px padding
            else:
                return
            # 额外 margin 抵消 QAbstractItemView padding + border
            padding = 14  # 6px*2 padding + 2px border
            max_h = int(row_h * max_items + padding)
            # 直接约束 popup 容器（QComboBoxPrivateContainer），
            # 仅设 view.setMaximumHeight 可能被容器 resize 覆盖。
            # ⚠ 不设 view 的 maximumHeight/fixedHeight，否则干扰
            # QListView 内置的 scrollbar 触发逻辑。
            popup = view.parentWidget()
            if popup and popup is not self:
                popup.setFixedHeight(max_h)
        except Exception:
            pass

    def _apply_popup_style(self):
        """延迟应用 popup 样式 — 在 view 完全展示后执行"""
        try:
            from app.utils.design_tokens import ComboBoxStyles, Colors
            from PySide6.QtGui import QPalette, QColor
            Colors.refresh()
            view = self.view()
            view.setStyleSheet(ComboBoxStyles.dark_combo_dropdown())
            palette = view.palette()
            palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.TEXT_ACCENT))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
            view.setPalette(palette)
            view.update()
        except Exception:
            pass


class TextEdit(QTextEdit):
    """文本编辑框 — 暗色精工工业风统一样式

    使用 QTextEdit（与 qfluentwidgets 原版一致），而非 QPlainTextEdit。
    QTextEdit 使用 QTextDocumentLayout，其 documentSize().height() 返回像素值，
    且布局计算是即时的（非惰性），避免 QPlainTextDocumentLayout 的行数/像素混淆
    和惰性布局导致的换行计数为 0 的问题。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        from app.utils.design_tokens import InputStyles
        self.setStyleSheet(InputStyles.text_edit_textedit())


class SingleDirectionScrollArea(QScrollArea):
    """单向滚动区域"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)


class ScrollArea(QScrollArea):
    """透明滚动区域（P0 移植缺口：插件用）

    提供与 qfluentwidgets ScrollArea 兼容的透明背景 + enableTransparentBackground API。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        self.viewport().setStyleSheet("background: transparent;")

    def enableTransparentBackground(self):
        """使滚动区域与内容背景透明"""
        self.setStyleSheet("QScrollArea{border: none; background: transparent}")
        if self.widget():
            self.widget().setStyleSheet("QWidget{background: transparent}")


class MessageBox(QDialog):
    """消息对话框"""

    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_lbl)

        content_lbl = QLabel(content)
        content_lbl.setWordWrap(True)
        layout.addWidget(content_lbl)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.yesButton = PrimaryPushButton("确定")
        self.cancelButton = PushButton("取消")
        btn_layout.addWidget(self.cancelButton)
        btn_layout.addWidget(self.yesButton)
        layout.addLayout(btn_layout)

        self.yesButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        self.setFixedSize(400, 200)

    def exec(self):
        return super().exec()

    def setText(self, text):
        pass  # 兼容 API


class Dialog(QDialog):
    """对话框"""
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        content_lbl = QLabel(content)
        content_lbl.setWordWrap(True)
        layout.addWidget(content_lbl)

        self.yesButton = PrimaryPushButton("确定")
        self.cancelButton = PushButton("取消")
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancelButton)
        btn_layout.addWidget(self.yesButton)
        layout.addLayout(btn_layout)
        self.yesButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)



class SwitchButton(QPushButton):
    """开关按钮 - QPainter 渲染，滑块动画

    仿 qfluentwidgets 的 Indicator 实现。
    使用 QPushButton(checkable) 基类，Qt 原生处理鼠标交互，规避 C 层栈溢出。
    """
    checkedChanged = Signal(bool)

    # ── 尺寸常量 ────────────────────────────
    _W = 42
    _H = 22
    _SLIDER = 12              # 滑块直径
    _MARGIN = 5               # 滑块到边缘
    _BORDER = 1

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self._on_text = text
        self._off_text = ""

        # 滑块位置（QPropertyAnimation 驱动）
        self._slider_x = float(self._MARGIN)

        # 动画
        self._slide_ani = QPropertyAnimation(self, b"slider_x")
        self._slide_ani.setDuration(120)
        self._slide_ani.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setFixedSize(self._W, self._H)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        # Qt 的 toggled → 动画 + 兼容信号
        self.toggled.connect(self._on_toggled)
        self.toggled.connect(lambda c: self.checkedChanged.emit(c))

    # ── API 兼容 ────────────────────────────

    def setOnText(self, text: str):
        self._on_text = text

    def setOffText(self, text: str):
        self._off_text = text

    def isChecked(self) -> bool:
        return super().isChecked()

    def setChecked(self, checked: bool):
        """QPushButton.setChecked → emits toggled → triggers our handlers"""
        super().setChecked(checked)

    def toggle(self):
        super().toggle()

    def toggleChecked(self):
        self.toggle()

    # ── 动画 ─────────────────────────────────

    def _on_toggled(self, checked: bool):
        """Qt 内置信号驱动动画"""
        target = float(self._slider_target_x())
        self._slide_ani.stop()
        self._slide_ani.setEndValue(target)
        self._slide_ani.start()

    def _slider_target_x(self) -> int:
        if self.isChecked():
            return self._W - self._SLIDER - self._MARGIN
        return self._MARGIN

    def get_slider_x(self) -> float:
        return self._slider_x

    def set_slider_x(self, x: float):
        self._slider_x = max(x, float(self._MARGIN))
        self.update()

    slider_x = Property(float, get_slider_x, set_slider_x)

    # ── 颜色（实时读 design_tokens 以跟随主题）───

    @staticmethod
    def _accent() -> QColor:
        from app.utils.design_tokens import Colors
        c = Colors.TEXT_ACCENT
        return QColor(c) if c else QColor("#66c6ff")

    @staticmethod
    def _border() -> QColor:
        from app.utils.design_tokens import Colors
        c = Colors.BORDER
        return QColor(c) if c else QColor("#3d4a60")

    # ── 绘制 ─────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 居中偏移：适应 setFixedWidth(50)
        x_off = (self.width() - self._W) // 2
        y_off = (self.height() - self._H) // 2

        self._draw_bg(painter, x_off, y_off)
        self._draw_knob(painter, x_off, y_off)

    def _draw_bg(self, p: QPainter, xo: int, yo: int):
        r = self._H / 2
        rect = QRectF(xo + self._BORDER, yo + self._BORDER,
                      self._W - 2 * self._BORDER, self._H - 2 * self._BORDER)

        if self.isChecked():
            color = self._accent()
            if not self.isEnabled():
                color = QColor(0, 0, 0, 0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
        else:
            bc = self._border()
            if not self.isEnabled():
                bc = QColor(255, 255, 255, 41)
            elif self.underMouse():
                bc = bc.lighter(130)
            p.setPen(bc)
            p.setBrush(QColor(0, 0, 0, 0))

        p.drawRoundedRect(rect, r, r)

    def _draw_knob(self, p: QPainter, xo: int, yo: int):
        cx = xo + self._slider_x + self._SLIDER / 2
        cy = yo + self._H / 2
        r = self._SLIDER / 2

        if self.isChecked():
            c = QColor(Qt.GlobalColor.white)
            if not self.isEnabled():
                c = QColor(255, 255, 255, 77)
        else:
            c = QColor(255, 255, 255, 201)
            if not self.isEnabled():
                c = QColor(255, 255, 255, 96)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(cx, cy), r, r)


class SettingCard(QFrame):
    """设置卡片基类（QPainter 渲染）"""
    def __init__(self, icon=None, title="", content="", parent=None):
        super().__init__(parent)
        # 外层垂直布局：header 在上，expandable view 在下
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)

        # 头部水平布局：图标 + 标题 + 描述 + 伸缩 + 操作按钮
        self.hBoxLayout = QHBoxLayout()
        self.hBoxLayout.setSpacing(8)
        self.hBoxLayout.setContentsMargins(20, 14, 16, 14)
        self.hBoxLayout.setAlignment(Qt.AlignVCenter)

        self.iconWidget = IconWidget(icon, self) if icon and not icon.isNull() else None
        if self.iconWidget:
            self.iconWidget.setFixedSize(16, 16)
            self.iconWidget.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.hBoxLayout.addWidget(self.iconWidget, 0, Qt.AlignLeft)
            self.hBoxLayout.addSpacing(16)

        self.titleLabel = QLabel(title, self)
        self.titleLabel.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._title_base_size = 14
        self._content_base_size = 12
        self.contentLabel = QLabel(content or '', self)
        self.contentLabel.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._refresh_label_styles()

        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setAlignment(Qt.AlignVCenter)
        text_layout.addWidget(self.titleLabel, 0, Qt.AlignLeft)
        text_layout.addWidget(self.contentLabel, 0, Qt.AlignLeft)
        self.hBoxLayout.addLayout(text_layout)
        self.hBoxLayout.addSpacing(16)
        self.hBoxLayout.addStretch(1)

        self.vBoxLayout.addLayout(self.hBoxLayout)

        self.viewLayout = self.hBoxLayout   # 兼容 qfluentwidgets（子类向此添加操作控件）

    def _refresh_label_styles(self):
        """刷新标题和描述文字的样式（跟随字号设置）"""
        from app.utils.design_tokens import font_size_css
        self.titleLabel.setStyleSheet(
            f"{font_size_css(self._title_base_size)} font-weight: 600;"
        )
        self.contentLabel.setStyleSheet(
            f"{font_size_css(self._content_base_size)} color: #888;"
        )

    def refresh_style(self):
        """刷新卡片样式（主题/字号切换时调用）"""
        self._refresh_label_styles()

    def _cardBg(self):
        if isDarkTheme():
            return QColor(255, 255, 255, 25), QColor(0, 0, 0, 50)
        return QColor(255, 255, 255, 170), QColor(0, 0, 0, 19)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        bg, border = self._cardBg()
        painter.setBrush(bg)
        painter.setPen(border)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

    def addWidget(self, widget, stretch=0, alignment=Qt.AlignmentFlag.AlignLeft):
        """添加 widget 到卡片头部右侧"""
        self.hBoxLayout.addWidget(widget, stretch, alignment)


class OptionsSettingCard(SettingCard):
    optionChanged = Signal(str)  # 兼容 qfluentwidgets

    def __init__(self, configItem, icon, title, content, texts=None, parent=None):
        # qfluentwidgets 签名: (configItem, icon, title, content, texts, parent)
        super().__init__(icon, title, content, parent)
        self.configItem = configItem
        items = texts or []
        if callable(items):
            items = getattr(items, 'default', [])
        self.combo = ComboBox()
        self.combo.addItems(items if isinstance(items, list) else [])
        self.combo.currentTextChanged.connect(self.optionChanged)
        self.hBoxLayout.addWidget(self.combo)
        self.option = self.combo  # 兼容


class ExpandSettingCard(SettingCard):
    """可展开的设置卡片（点击卡片空白处展开/折叠）"""
    def __init__(self, icon=None, title="", content="", parent=None):
        super().__init__(icon, title, content, parent)
        self.card = self
        self._is_expanded = False

        # 展开内容区域（子类向 viewLayout 添加控件）
        self.view = QWidget()
        self.view.setVisible(False)
        self.view.setMaximumHeight(0)
        self.viewLayout = QVBoxLayout(self.view)
        self.viewLayout.setContentsMargins(48, 0, 16, 8)
        self.viewLayout.setSpacing(4)
        self.view.setStyleSheet("background-color: transparent;")

        # 将 view 添加到卡片底部（垂直布局中，位于 header 下方）
        self.vBoxLayout.addWidget(self.view)

        # 下拉动画
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_anim_value)
        self._animation.finished.connect(self._on_anim_finished)

        # 不可点击的展开/折叠图标（最右侧）
        self._expand_icon = QLabel(self)
        self._expand_icon.setFixedSize(16, 16)
        self._expand_icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._update_expand_icon()
        self.hBoxLayout.addWidget(self._expand_icon)
        # 兼容别名：qfluentwidgets ExpandSettingCard 的 expandButton（可点击按钮）。
        # shim 版展开交互走 mouseReleaseEvent 点击卡片空白处，_expand_icon 仅作
        # 视觉指示；部分子类（如 HookListSettingCard._update_button_position）用
        # expandButton 作为布局位置锚点，提供别名避免 AttributeError。
        self.expandButton = self._expand_icon

    def addWidget(self, widget, stretch=0, alignment=Qt.AlignmentFlag.AlignLeft):
        """添加 widget 到展开图标左侧，确保展开图标始终在右侧"""
        idx = self.hBoxLayout.indexOf(self._expand_icon)
        if idx >= 0:
            self.hBoxLayout.insertWidget(idx, widget, stretch, alignment)
        else:
            super().addWidget(widget, stretch, alignment)

    def _update_expand_icon(self):
        """更新展开/折叠图标"""
        icon_name = "折叠.svg" if self._is_expanded else "展开.svg"
        icon = QIcon(f":/icons/{icon_name}")
        if not icon.isNull():
            self._expand_icon.setPixmap(icon.pixmap(16, 16))
        else:
            self._expand_icon.setText("▲" if self._is_expanded else "▼")

    def mouseReleaseEvent(self, e):
        """点击卡片展开/折叠（展开状态下点击 view 内容区不触发展/收）"""
        # 仅在 view 区域外（header 区域）点击时才切换
        if not self._is_expanded or not self.view.geometry().contains(e.position().toPoint()):
            self._toggle_expand()
        super().mouseReleaseEvent(e)

    def _toggle_expand(self):
        # 停止正在运行的动画，立即响应新操作
        self._animation.stop()
        if self._is_expanded:
            self._is_expanded = False
            self._animation.setStartValue(self.view.height())
            self._animation.setEndValue(0)
            self._animation.start()
        else:
            self._is_expanded = True
            self.view.setVisible(True)
            self.view.setMaximumHeight(16777215)
            self.view.adjustSize()
            target_height = self.view.sizeHint().height()
            self._animation.setStartValue(0)
            self._animation.setEndValue(target_height)
            self._animation.start()
        self._update_expand_icon()

    def _on_anim_value(self, value):
        self.view.setMaximumHeight(int(value))

    def _on_anim_finished(self):
        if not self._is_expanded:
            self.view.setVisible(False)
            self.view.setMaximumHeight(0)
        else:
            self.view.setMaximumHeight(16777215)
        self._adjustViewSize()

    def _adjustViewSize(self):
        if self.parent():
            self.parent().adjustSize()

    @property
    def isExpand(self):
        return self._is_expanded


class SegmentedWidget(QTabBar):
    """分段选择控件"""
    currentItemChanged = Signal(str, str)  # (old_text, new_text)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._route_keys: dict[str, int] = {}  # routeKey → tab index
        self.setStyleSheet("""
            QTabBar::tab {
                padding: 6px 16px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        self.currentChanged.connect(self._on_current_changed)

    def _on_current_changed(self, index):
        """将 QTabBar.currentChanged(int) 桥接到 currentItemChanged(str, str)"""
        old_text = self.tabText(max(0, index - 1)) if index > 0 else ""
        new_text = self.tabText(index)
        self.currentItemChanged.emit(old_text, new_text)

    def addItem(self, routeKey: str, text: str = None):
        """兼容 qfluentwidgets 的 addItem 方法

        支持两种调用方式：
        - addItem(text)            — 单参数（仅文本）
        - addItem(routeKey, text)  — 双参数（路由键 + 文本）
        """
        if text is None:
            text = routeKey
        idx = self.addTab(text)
        self._route_keys[routeKey] = idx
        return idx

    def setCurrentItem(self, routeKey: str):
        """按 routeKey 选中对应的 tab（兼容 qfluentwidgets）"""
        idx = self._route_keys.get(routeKey)
        if idx is not None:
            self.setCurrentIndex(idx)


class Pivot(QWidget):
    """Pivot 横向标签页切换控件（routeKey 驱动，信号发射 routeKey）

    兼容 qfluentwidgets Pivot 契约：
    - Pivot(header) 实例化（header 为可选标题/父窗口参数）
    - addItem(routeKey, text, icon=None, onClick=None)
    - setCurrentItem(routeKey) 高亮当前项
    - currentItemChanged = Signal(str)：发射 routeKey（非显示文本，供路由跳转）
    """

    currentItemChanged = Signal(str)  # routeKey

    def __init__(self, header=None, parent=None):
        # 兼容两种调用：Pivot(header) / Pivot(parent)
        if isinstance(header, QWidget) and parent is None:
            parent = header
            header = None
        super().__init__(parent)
        self._header = header
        self._route_keys: list = []
        self._buttons: dict = {}
        self._current: str = ""
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self.setStyleSheet("""
            Pivot QPushButton {
                background: transparent;
                border: none;
                padding: 6px 14px;
                color: palette(text);
                border-bottom: 2px solid transparent;
            }
            Pivot QPushButton:checked {
                color: #0078d4;
                border-bottom: 2px solid #0078d4;
            }
            Pivot QPushButton:hover {
                background: palette(alternate-base);
                border-radius: 4px;
            }
        """)

    def addItem(self, routeKey: str, text: str = None, icon=None, onClick=None):
        """添加一个 pivot 项

        Args:
            routeKey: 路由键（setCurrentItem/currentItemChanged 使用）
            text: 显示文本（为 None 时使用 routeKey）
            icon: QIcon 或 None
            onClick: 点击回调（可选）
        """
        if text is None:
            text = routeKey
        btn = QPushButton(text, self)
        if icon is not None:
            btn.setIcon(icon)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.setCurrentItem(routeKey))
        if onClick is not None:
            btn.clicked.connect(onClick)
        self._route_keys.append(routeKey)
        self._buttons[routeKey] = btn
        self._layout.addWidget(btn)
        if not self._current:
            self.setCurrentItem(routeKey)
        return btn

    def setCurrentItem(self, routeKey: str):
        """按 routeKey 高亮当前项并发射 currentItemChanged（仅变化时）"""
        if routeKey not in self._buttons:
            return
        if self._current == routeKey:
            # 仍同步选中状态（如按钮被直接点击）
            for k, b in self._buttons.items():
                b.setChecked(k == routeKey)
            return
        old = self._current
        self._current = routeKey
        for k, b in self._buttons.items():
            b.setChecked(k == routeKey)
        if old != routeKey:
            self.currentItemChanged.emit(routeKey)

    def currentItem(self) -> str:
        """返回当前 routeKey"""
        return self._current


class FluentLabelBase(QLabel):
    """标签基类（供插件 isinstance 判断统一字体处理）

    兼容 qfluentwidgets 的 FluentLabelBase：所有标签类继承此基类，
    插件通过 isinstance(child, FluentLabelBase) 识别文字标签统一设置字体。
    """

    def __init__(self, text="", parent=None):
        # 兼容：第一个参数是 parent widget 而非文本
        if isinstance(text, QWidget) and parent is None:
            parent = text
            text = ""
        super().__init__(text, parent)


class BodyLabel(FluentLabelBase):
    """正文标签"""

    def __init__(self, text="", parent=None):
        if isinstance(text, QWidget) and parent is None:
            parent = text
            text = ""
        super().__init__(text, parent)


class SimpleCardWidget(QFrame):
    """简单卡片控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            SimpleCardWidget {
                background-color: palette(base);
                border: 1px solid palette(midlight);
                border-radius: 8px;
            }
        """)
        self.vBoxLayout = QVBoxLayout(self)


class CardSeparator(QFrame):
    """卡片分割线"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setStyleSheet("color: palette(midlight);")


class EditableComboBox(QComboBox):
    """可编辑组合框 — 暗色精工工业风统一样式

    与 ComboBox 同样的弹出方向修复 + view 样式刷新。

    高度修复：
    - 可编辑模式下内部 QLineEdit 有独立 padding，与 QComboBox 自身的
      padding 叠加会导致编辑区高度坍缩为「2 格」。
    - 修复方式：降低内部 QLineEdit padding，同时增大 QComboBox 的
      min-height，保证编辑区视觉舒适。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self._apply_style()
        # 限制下拉可见项数（与 ComboBox 同理，放在 __init__ 而非 _apply_style()）
        self.setMaxVisibleItems(8)
        # 注：minimumSizeHint 已在下面重写，不再基于最长下拉项，
        # 防止窄布局中右侧按钮被溢出遮挡。
        # 注册主题重载回调 → 重新应用样式以反映新主题色
        self._theme_reload_cb = None
        try:
            from app.utils.theme_manager import theme_manager
            self._theme_reload_cb = self._refresh_theme_style
            theme_manager.on_reload(self._theme_reload_cb)
        except Exception:
            pass

    def _refresh_theme_style(self):
        """主题切换时立即刷新样式（不等下次 popup）"""
        try:
            from app.utils.design_tokens import Colors
            Colors.refresh()
            self._apply_style()
            self._apply_popup_style()
            # 强制 Qt 重算缓存的 style（否则 frame 背景停在旧主题）
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()
        except Exception:
            pass

    def destroy(self, destroyWindow=True, destroySubWindows=True):
        if self._theme_reload_cb is not None:
            try:
                from app.utils.theme_manager import theme_manager
                theme_manager.remove_reload_callback(self._theme_reload_cb)
            except Exception:
                pass
            self._theme_reload_cb = None
        super().destroy(destroyWindow, destroySubWindows)

    def minimumSizeHint(self):
        """重写最小尺寸提示：不再基于最长下拉项，防止窄布局溢出

        与 ComboBox.minimumSizeHint 相同的逻辑，仅基于当前文本
        计算最小宽度，不被长模型名/URL 撑大导致右侧按钮被遮挡。
        """
        hint = super().minimumSizeHint()
        fm = self.fontMetrics()
        text_w = fm.horizontalAdvance(self.currentText())
        hint.setWidth(max(text_w + 64, 80))
        return hint

    def _apply_style(self):
        from app.utils.design_tokens import ComboBoxStyles, Colors, font_size_css, get_font_family_css
        Colors.refresh()
        # 基础 combo 样式，但提升 min-height 以容纳内部 QLineEdit
        base = ComboBoxStyles.dark_combo()
        base = base.replace("min-height: 28px;", "min-height: 32px;", 1)  # 只改 QComboBox 本体，不改 ::item
        self.setStyleSheet(
            base
            + f"""
            QComboBox QLineEdit {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.TEXT_ACCENT};
                selection-color: {Colors.BUTTON_TEXT_ON_ACCENT};
                padding: 2px 4px;
                min-height: 28px;
                {font_size_css(12)}
                {get_font_family_css()}
            }}
        """
        )
        # 自定义委托显式绘制 hover/selected（Fusion 限制）。
        # 传入 self 让委托能用 currentIndex() 区分"实际选中"与"hover 预览"。
        self.view().setItemDelegate(ComboItemDelegate(combo=self, parent=self.view()))

    def _constrain_popup_height(self, view):
        """手动约束下拉 popup 容器的高度（与 ComboBox._constrain_popup_height 相同实现）"""
        try:
            max_items = self.maxVisibleItems()
            count = self.count()
            if count <= max_items:
                return
            if count > 0:
                row_h = view.sizeHintForRow(0)
                if row_h <= 0:
                    row_h = 36
            else:
                return
            padding = 14
            max_h = int(row_h * max_items + padding)
            popup = view.parentWidget()
            if popup and popup is not self:
                popup.setFixedHeight(max_h)
        except Exception:
            pass

    def _constrain_popup_horizontally(self, popup):
        """将 popup 的水平位置约束在屏幕可用区域内，防止右侧溢出屏幕"""
        try:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.screenAt(popup.geometry().center()) or QGuiApplication.primaryScreen()
            if not screen:
                return
            screen_rect = screen.availableGeometry()
            pr = popup.geometry()
            if pr.right() > screen_rect.right():
                popup.move(screen_rect.right() - pr.width(), pr.y())
            if pr.left() < screen_rect.left():
                popup.move(screen_rect.left(), pr.y())
        except Exception:
            pass

    def wheelEvent(self, event):
        """禁用滚轮切换 — 避免鼠标悬停时滚动误触改变值"""
        event.ignore()

    def showPopup(self):
        super().showPopup()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_popup_style)
        v = self.view()
        v.scrollToTop()
        self._constrain_popup_height(v)
        popup = v.parentWidget()
        if popup and popup is not self:
            pt = self.mapToGlobal(self.rect().bottomLeft())
            popup.move(popup.x(), pt.y())
            # 约束：下拉框不超出屏幕可视区域（右边界）
            self._constrain_popup_horizontally(popup)

    def _apply_popup_style(self):
        try:
            from app.utils.design_tokens import ComboBoxStyles, Colors
            from PySide6.QtGui import QPalette, QColor
            Colors.refresh()
            view = self.view()
            view.setStyleSheet(ComboBoxStyles.dark_combo_dropdown())
            palette = view.palette()
            palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.TEXT_ACCENT))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
            view.setPalette(palette)
            view.update()
        except Exception:
            pass


class ListWidget(QListWidget):
    """列表控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QListWidget {
                background: transparent;
                color: palette(windowText);
                border: none;
                border-radius: 6px;
                outline: none;
            }
            QListWidget::item {
                border-radius: 4px;
                padding: 6px 12px;
            }
            QListWidget::item:selected {
                background: palette(highlight);
                color: palette(highlightedText);
            }
            QListWidget::item:hover:!selected {
                background: rgba(128, 128, 128, 0.1);
            }
            QListWidget::item:selected:!active {
                background: palette(midlight);
            }
        """)


class SpinBox(QSpinBox):
    """数字选择框 — 暗色精工工业风统一样式"""
    def __init__(self, parent=None):
        super().__init__(parent)
        from app.utils.design_tokens import SpinBoxStyles
        self.setStyleSheet(SpinBoxStyles.spin_box())


class StrongBodyLabel(FluentLabelBase):
    """强调正文标签"""
    def __init__(self, text="", parent=None):
        # 兼容：第一个参数是 parent widget 而非文本
        if isinstance(text, QWidget) and parent is None:
            parent = text
            text = ""
        super().__init__(text, parent)
        self.setStyleSheet("font-weight: bold;")


class ToolButton(QPushButton):
    """工具按钮"""
    def __init__(self, icon=None, parent=None):
        # 兼容：第一个参数是 parent widget 而非 QIcon
        if isinstance(icon, QWidget) and parent is None:
            parent = icon
            icon = None
        super().__init__(parent)
        if isinstance(icon, QIcon):
            self.setIcon(icon)
        self.setFixedSize(36, 36)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(128, 128, 128, 0.1);
            }
        """)


# ============ 额外组件 ============

class CaptionLabel(FluentLabelBase):
    """说明文字标签"""
    def __init__(self, text="", parent=None):
        if isinstance(text, QWidget) and parent is None:
            parent = text
            text = ""
        super().__init__(text, parent)
        self.setStyleSheet("font-size: 12px; color: gray;")


class CardWidget(QFrame):
    """卡片控件（QPainter 渲染 + hover/pressed 效果）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._borderRadius = 8
        self._isHover = False
        self._isPressed = False
        self.setMouseTracking(True)

    def _bgColor(self):
        if self._isPressed:
            alpha = 8 if isDarkTheme() else 64
        elif self._isHover:
            alpha = 21 if isDarkTheme() else 64
        else:
            alpha = 13 if isDarkTheme() else 170
        return QColor(255, 255, 255, alpha)

    def _borderColor(self):
        if isDarkTheme():
            return QColor(255, 255, 255, 20)
        return QColor(0, 0, 0, 12)

    def enterEvent(self, e):
        self._isHover = True; self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._isHover = False; self._isPressed = False; self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._isPressed = True; self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._isPressed = False; self.update()
        super().mouseReleaseEvent(e)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(self._borderColor())
        painter.setBrush(self._bgColor())
        r = self._borderRadius
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), r, r)


class SimpleCardWidget(CardWidget):
    """简单卡片控件（无交互变色，固定背景）"""
    def __init__(self, parent=None):
        super().__init__(parent)

    def _bgColor(self):
        return QColor(255, 255, 255, 13 if isDarkTheme() else 170)

    def _borderColor(self):
        if isDarkTheme():
            return QColor(255, 255, 255, 20)
        return QColor(0, 0, 0, 12)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setPen(self._borderColor())
        painter.setBrush(self._bgColor())
        r = self._borderRadius
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), r, r)


class CardSeparator(QWidget):
    """卡片分割线（QPainter 渲染）"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(3)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        if isDarkTheme():
            painter.setPen(QColor(255, 255, 255, 46))
        else:
            painter.setPen(QColor(0, 0, 0, 12))
        painter.drawLine(2, 1, self.width() - 2, 1)


class ConfigItem:
    """配置项占位"""
    def __init__(self, key, default=None):
        self.key = key
        self.default = default
        self._value = default
        self.valueChanged = Signal()

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v
        self.valueChanged.emit(v)

    def set(self, value, save=False):
        self.value = value


class ConfigValidator:
    """配置验证器占位"""
    def validate(self, value):
        return True

    def correct(self, value):
        return value


class BoolValidator(ConfigValidator):
    """布尔值验证器（P1 配置体系）"""
    def validate(self, value):
        return isinstance(value, bool)

    def correct(self, value):
        return bool(value)


class OptionsValidator(ConfigValidator):
    """选项枚举验证器（P1 配置体系）"""
    def __init__(self, options):
        self.options = options

    def validate(self, value):
        return value in self.options

    def correct(self, value):
        return value if value in self.options else (self.options[0] if self.options else value)


class RangeValidator(ConfigValidator):
    """数值范围验证器（P1 配置体系）"""
    def __init__(self, min_, max_):
        self.min = min_
        self.max = max_

    def validate(self, value):
        try:
            return self.min <= value <= self.max
        except TypeError:
            return False

    def correct(self, value):
        try:
            if value < self.min:
                return self.min
            if value > self.max:
                return self.max
        except TypeError:
            pass
        return value


class OptionsConfigItem(ConfigItem):
    """选项配置项（P1 配置体系，映射 ConfigItem）"""
    def __init__(self, key, default, options, restart=False, validator=None):
        super().__init__(key, default)
        self.options = options
        self.restart = restart
        self.validator = validator or OptionsValidator(options)


class RangeConfigItem(ConfigItem):
    """数值范围配置项（P1 配置体系，映射 ConfigItem）"""
    def __init__(self, key, default, min_, max_, restart=False, validator=None):
        super().__init__(key, default)
        self.restart = restart
        self.validator = validator or RangeValidator(min_, max_)


class LineEdit(QLineEdit):
    """行编辑框 — 暗色精工工业风统一样式"""
    def __init__(self, parent=None):
        super().__init__(parent)
        from app.utils.design_tokens import InputStyles
        self.setStyleSheet(InputStyles.line_edit())


class PasswordLineEdit(QLineEdit):
    """密码输入框 — 暗色精工工业风统一样式"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        from app.utils.design_tokens import InputStyles
        self.setStyleSheet(InputStyles.line_edit())


class PrimaryToolButton(ToolButton):
    """主工具按钮"""
    pass


class Slider(QSlider):
    """滑动条 — 暗色精工工业风统一样式

    兼容 QSlider 的两种构造签名：
        Slider(parent=None)
        Slider(orientation, parent=None)
    """
    def __init__(self, orientation=None, parent=None):
        if isinstance(orientation, Qt.Orientation):
            # Slider(orientation, parent) 风格
            super().__init__(parent)
            self.setOrientation(orientation)
        else:
            # Slider(parent) 风格 — 第一个参数实际上是 parent
            super().__init__(orientation)
        from app.utils.design_tokens import SliderStyles
        self.setStyleSheet(SliderStyles.slider())


class ToolTipFilter(QObject):
    """工具提示过滤器 - 为 widget 添加自定义 tooltip 行为"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)


class Theme:
    """主题枚举"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


# 模块级主题状态跟踪
_theme_mode = Theme.LIGHT


def getIconColor():
    """获取图标颜色（根据当前主题返回合适颜色）"""
    if _theme_mode == Theme.DARK:
        return QColor(180, 180, 180)
    return QColor(80, 80, 80)


def setTheme(theme):
    """设置主题 - QPalette + QSS 实现完整的深色/浅色主题"""
    global _theme_mode
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette, QColor

    app = QApplication.instance()
    if app is None:
        _theme_mode = theme
        return

    _theme_mode = theme

    if theme == Theme.DARK:
        # 深色调色板
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
        palette.setColor(QPalette.Base, QColor(37, 37, 38))
        palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
        palette.setColor(QPalette.ToolTipBase, QColor(50, 50, 50))
        palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
        palette.setColor(QPalette.Text, QColor(224, 224, 224))
        palette.setColor(QPalette.Button, QColor(55, 55, 55))
        palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
        palette.setColor(QPalette.BrightText, QColor(255, 80, 80))
        palette.setColor(QPalette.Link, QColor(53, 247, 138))
        palette.setColor(QPalette.Highlight, QColor(53, 247, 138))
        palette.setColor(QPalette.HighlightedText, QColor(224, 224, 224))
        # 关键：显式设置 Mid/Midlight/Light/Dark，防止 Qt 自动计算为白色
        palette.setColor(QPalette.Light, QColor(100, 100, 100))
        palette.setColor(QPalette.Midlight, QColor(75, 75, 75))
        palette.setColor(QPalette.Mid, QColor(65, 65, 65))
        palette.setColor(QPalette.Dark, QColor(40, 40, 40))
        palette.setColor(QPalette.Shadow, QColor(20, 20, 20))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
        app.setPalette(palette)
        # 深色 QSS 细化
        app.setStyleSheet("""
            QToolTip {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.04);
                width: 8px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.28);
                border-radius: 4px;
                min-height: 28px;
                margin: 0 1px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(102,198,255,0.50);
            }
            QScrollBar::handle:vertical:pressed {
                background: rgba(102,198,255,0.70);
            }
            QScrollBar:horizontal {
                background: rgba(255,255,255,0.04);
                height: 8px;
                margin: 0 2px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255,255,255,0.28);
                border-radius: 4px;
                min-width: 28px;
                margin: 1px 0;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(102,198,255,0.50);
            }
            QScrollBar::handle:horizontal:pressed {
                background: rgba(102,198,255,0.70);
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                height: 0;
                width: 0;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QHeaderView::section {
                background-color: #333;
                color: #e0e0e0;
                border: 1px solid #444;
                padding: 4px;
            }
        """)
    else:
        # 浅色主题：重置为系统默认调色板
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet("")


def isDarkTheme():
    """判断是否为暗色主题"""
    return _theme_mode == Theme.DARK


class SwitchSettingCard(SettingCard):
    """开关设置卡片"""
    def __init__(self, icon, title, content, configItem_or_checked=None, parent=None, configItem=None):
        # 兼容：configItem 作为关键字参数或位置参数
        actual_config = configItem if configItem is not None else configItem_or_checked
        super().__init__(icon, title, content, parent)
        self.configItem = actual_config
        self.switch = SwitchButton(self)
        self.viewLayout.addWidget(self.switch) if hasattr(self, 'viewLayout') else self.layout().addWidget(self.switch)
        self.checkedChanged = self.switch.checkedChanged

        # 从配置项读取初始状态
        if self.configItem is not None:
            try:
                self.switch.setChecked(bool(self.configItem.value))
            except Exception:
                pass
            # 开关变更时同步到配置并保存
            self.switch.checkedChanged.connect(self._on_switch_changed)

    # ── 兼容别名（部分外部代码通过 .switchButton 访问）───
    @property
    def switchButton(self):
        return self.switch

    def _on_switch_changed(self, checked):
        """开关状态变更时同步到 ConfigItem 并持久化"""
        if self.configItem is None:
            return
        try:
            self.configItem.value = checked
            # 保存到配置文件
            if hasattr(self.configItem, '_obj') and hasattr(self.configItem._obj, 'save'):
                self.configItem._obj.save()
        except Exception:
            pass


class MessageBoxBase(QDialog):
    """消息对话框基类"""
    def __init__(self, title="", content="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        self.contentLabel = QLabel(content)
        layout.addWidget(self.contentLabel)
        self.yesButton = PrimaryPushButton("确定")
        self.cancelButton = PushButton("取消")
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancelButton)
        btn_layout.addWidget(self.yesButton)
        layout.addLayout(btn_layout)
        self.yesButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)
        self.vBoxLayout = layout
        self.yesSignal = self.yesButton.clicked

    def exec(self):
        return super().exec()


class MaskDialogBase(QDialog):
    """带半透明遮罩的对话框基类（P0 移植缺口：原项目 10 处用）

    仿 qfluentwidgets MaskDialogBase 纯 PySide6 实现：
    - 半透明遮罩（windowMask，黑/白色半透明）
    - 居中圆角卡片（widget，QFrame）
    - 可拖拽（widget 空白处按下拖动）
    - 点击遮罩关闭开关（setClosableOnMaskClicked）
    - 阴影（setShadowEffect）与遮罩颜色（setMaskColor）

    子类用法（参考原项目 common_dialogs.py / memory_card.py）：
        super().__init__(parent)
        self.setShadowEffect(60, (0, 10), QColor(0, 0, 0, 100))
        self.setClosableOnMaskClicked(True)
        self.setDraggable(True)
        self.setMaskColor(QColor(0, 0, 0, 76))
        self.widget.setObjectName("myDialog")
        self.widget.setStyleSheet(...)
        layout = QVBoxLayout(self.widget); ...
        self.widget.setFixedSize(400, 240)
        # 居中：子类实现 _center_widget 并在 resizeEvent 中调用
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._isClosableOnMaskClicked = False
        self._isDraggable = False
        self._dragPos = QPoint()
        self._hBoxLayout = QHBoxLayout(self)
        self.windowMask = QWidget(self)

        # dialog box in the center of mask, all widgets take it as parent
        self.widget = QFrame(self, objectName='centerWidget')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 铺满父窗口（parent 为 None 时回退到屏幕可用区域大小）
        if parent is not None:
            self.setGeometry(0, 0, parent.width(), parent.height())
        else:
            screen = QApplication.primaryScreen()
            geo = screen.availableGeometry() if screen else QRect(0, 0, 800, 600)
            self.setGeometry(0, 0, geo.width(), geo.height())

        c = 0 if isDarkTheme() else 255
        self.windowMask.resize(self.size())
        self.windowMask.setStyleSheet(f'background:rgba({c}, {c}, {c}, 0.6)')
        self._hBoxLayout.addWidget(self.widget)
        self.setShadowEffect()

        self.window().installEventFilter(self)
        self.windowMask.installEventFilter(self)
        self.widget.installEventFilter(self)

    def setShadowEffect(self, blurRadius=60, offset=(0, 10), color=QColor(0, 0, 0, 100)):
        """为卡片 widget 添加阴影"""
        shadowEffect = QGraphicsDropShadowEffect(self.widget)
        shadowEffect.setBlurRadius(blurRadius)
        shadowEffect.setOffset(*offset)
        shadowEffect.setColor(color)
        self.widget.setGraphicsEffect(None)
        self.widget.setGraphicsEffect(shadowEffect)

    def setMaskColor(self, color):
        """设置遮罩颜色（QColor，含 alpha）"""
        self.windowMask.setStyleSheet(f"""
            background: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})
        """)

    def showEvent(self, e):
        """淡入动画"""
        opacityEffect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacityEffect)
        opacityAni = QPropertyAnimation(opacityEffect, b'opacity', self)
        opacityAni.setStartValue(0)
        opacityAni.setEndValue(1)
        opacityAni.setDuration(200)
        opacityAni.setEasingCurve(QEasingCurve.Type.InSine)
        opacityAni.finished.connect(lambda: self.setGraphicsEffect(None))
        opacityAni.start()
        super().showEvent(e)

    def done(self, code):
        """关闭（简化：无淡出动画，直接关闭）"""
        self.setGraphicsEffect(None)
        QDialog.done(self, code)

    def isClosableOnMaskClicked(self):
        return self._isClosableOnMaskClicked

    def setClosableOnMaskClicked(self, isClosable):
        self._isClosableOnMaskClicked = isClosable

    def setDraggable(self, draggable):
        self._isDraggable = draggable

    def isDraggable(self):
        return self._isDraggable

    def resizeEvent(self, e):
        self.windowMask.resize(self.size())

    def eventFilter(self, obj, e):
        if obj is self.window():
            if e.type() == QEvent.Type.Resize:
                self.resize(e.size())
        elif obj is self.windowMask:
            if e.type() == QEvent.Type.MouseButtonRelease and e.button() == Qt.MouseButton.LeftButton \
                    and self.isClosableOnMaskClicked():
                self.reject()
        elif obj is self.widget and self.isDraggable():
            if e.type() == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton:
                if not self.widget.childrenRegion().contains(e.pos()):
                    self._dragPos = e.pos()
                    return True
            elif e.type() == QEvent.Type.MouseMove and not self._dragPos.isNull():
                pos = self.widget.pos() + e.pos() - self._dragPos
                pos.setX(max(0, min(pos.x(), self.width() - self.widget.width())))
                pos.setY(max(0, min(pos.y(), self.height() - self.widget.height())))
                self.widget.move(pos)
                return True
            elif e.type() == QEvent.Type.MouseButtonRelease:
                self._dragPos = QPoint()

        return super().eventFilter(obj, e)


# ============ 工具函数 ============

def setFont(target, pointSize=None, weight=None):
    """设置字体 - 兼容 qfluentwidgets 的 setFont(widget, pointSize) 签名"""
    if isinstance(target, QWidget):
        widget = target
        size = pointSize
        if size is not None:
            font = widget.font()
            font.setPointSize(size)
            widget.setFont(font)
    elif isinstance(target, QFont):
        font = target
        if pointSize:
            font.setPointSize(pointSize)
        if weight:
            font.setWeight(weight)


def setFontFamilies(families):
    """设置全局字体族（简化实现）"""
    if families:
        font = QApplication.font()
        font.setFamilies(families)
        QApplication.setFont(font)


class _QConfigAccessor:
    """模拟 qfluentwidgets.qconfig 单例 - 委托给 Settings.get_instance()"""

    @staticmethod
    def _resolve(item):
        """从 item 解析出 _BoundConfigItem，兼容 ConfigItem 描述符和 _BoundConfigItem 两种传参"""
        from app.utils.config import Settings
        # 情况1: 直接传入 _BoundConfigItem
        if hasattr(item, '_item') and hasattr(item, '_obj'):
            return item
        # 情况2: 传入 ConfigItem 描述符，从实例获取
        if hasattr(item, '_name'):
            instance = Settings.get_instance()
            return getattr(instance, item._name, None)
        return None

    def get(self, item):
        """获取配置项的值"""
        if item is None:
            return None
        bound = self._resolve(item)
        if bound is not None:
            return bound.value
        return getattr(item, 'default', None)

    def set(self, item, value, save=False):
        """设置配置项的值

        Parameters
        ----------
        item: _BoundConfigItem
            配置项
        value: any
            新值
        save: bool
            是否立即保存到文件
        """
        if item is None:
            return
        bound = self._resolve(item)
        if bound is not None:
            bound.value = value
        if save:
            from app.utils.config import Settings
            Settings.get_instance().save()

    def getValidator(self, item):
        """获取配置项的验证器"""
        if hasattr(item, 'validator'):
            return item.validator
        return None


qconfig = _QConfigAccessor()