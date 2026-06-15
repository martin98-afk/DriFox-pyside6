from PySide6.QtCore import Qt, QStringListModel, QEvent
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QCompleter
from app.utils.fluent_shim import EditableComboBox, ComboItemDelegate
from app.utils.design_tokens import Colors, font_size_css, get_font_family_css


MAX_COMBO_VISIBLE_ITEMS = 8  # 下拉框最大同时显示数量

class SearchableEditableComboBox(EditableComboBox):
    def __init__(self, parent=None, max_visible_items: int = MAX_COMBO_VISIBLE_ITEMS):
        super().__init__(parent)
        self._max_visible_items = max_visible_items

        # 修复：不再调用 self.setStyleSheet() 覆盖父类（EditableComboBox）的完整样式。
        # 原本的代码会清空 QComboBox 外框样式，导致下拉框只显示「黑色框」。
        # 改为单独设置内部 QLineEdit 的样式，保留父类设置的 combo 外框 + 下拉按钮样式。
        Colors.refresh()
        le = self.lineEdit()
        if le:
            le.setStyleSheet(f"""
                background: transparent;
                border: none;
                color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.TEXT_ACCENT};
                selection-color: {Colors.BUTTON_TEXT_ON_ACCENT};
                padding: 0 4px;
                {font_size_css(12)}
                {get_font_family_css()}
            """)

        # 1. 使用私有变量名 _search_completer，避免覆盖基类的 completer() 方法
        self._search_completer = QCompleter(self)

        # 设置匹配模式为：包含匹配
        self._search_completer.setFilterMode(Qt.MatchContains)
        # 设置补全模式：弹出列表
        self._search_completer.setCompletionMode(QCompleter.PopupCompletion)
        self._search_completer.setCaseSensitivity(Qt.CaseInsensitive)

        # 2. 使用标准的 setCompleter 方法注册
        self.setCompleter(self._search_completer)

        # 3. 样式化 QCompleter 弹出列表（与父类 EditableComboBox 的 native dropdown 同色系）
        #    QCompleter 的 popup 是独立 Widget，不会继承 combo 的 view() 样式，
        #    必须单独设置 stylesheet（仅容器）+ 自定义委托（显式绘制 hover/selected，
        #    绕过 Fusion 不渲染 popup ::item:hover 的限制）。
        self._apply_completer_style()

        # 内部维护一个纯文本列表用于同步
        self._item_texts = []

        # 限制下拉列表同时显示的最大项数
        # ⚠ setMaxVisibleItems 是 QComboBox 的方法，不能调用 view()（QListView）上的同名方法
        self.setMaxVisibleItems(self._max_visible_items)

    def addItem(self, text: str, icon = None, userData=None):
        """重写单条添加"""
        super().addItem(text, icon, userData)
        # 去重处理（可选）
        if text not in self._item_texts:
            self._item_texts.append(text)
            self._update_completer_model()
        # 刷新最大显示项数
        self._apply_max_visible()

    def addItems(self, texts):
        """重写批量添加"""
        super().addItems(texts)
        # 这里的 texts 应该是从 Scanner 获取的所有类型列表
        self._item_texts = list(set(self._item_texts + list(texts)))
        self._update_completer_model()
        self._apply_max_visible()

    def _apply_max_visible(self):
        """应用最大显示项数限制"""
        # ⚠ setMaxVisibleItems 是 QComboBox 的方法，调用 view() 上的同名方法会 AttributeError
        self.setMaxVisibleItems(self._max_visible_items)

    def _apply_completer_style(self):
        """（重新）应用 QCompleter 弹出列表的暗色样式 + palette

        主题热切换时需要重新调用此方法刷新 completer popup 外观。
        """
        # 防御：widget 或其 QCompleter 可能已被销毁（如父窗口关闭后回调残留）
        import shiboken6
        if not shiboken6.isValid(self._search_completer):
            return
        Colors.refresh()
        completer_popup = self._search_completer.popup()
        if not completer_popup:
            return
        completer_popup.setStyleSheet(f"""
            QAbstractItemView {{
                background-color: {Colors.CONTENT_BG};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }}
            QAbstractItemView::item {{
                padding: 6px 12px;
                min-height: 24px;
                border-radius: 4px;
            }}
        """)
        completer_popup.setItemDelegate(ComboItemDelegate(combo=self, parent=completer_popup))
        pal = completer_popup.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor(Colors.TEXT_ACCENT))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
        completer_popup.setPalette(pal)
        # 安装事件过滤器以在每次弹出时约束位置
        completer_popup.installEventFilter(self)
        # 立即约束一次
        self._constrain_completer_popup(completer_popup)

    def _constrain_completer_popup(self, popup):
        """约束 completer 弹出列表不超出屏幕可视区域（右边界）"""
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

    def eventFilter(self, obj, event):
        """拦截 completer popup 的 Show 事件，重新约束其屏幕位置"""
        if event.type() == QEvent.Show and obj is self._search_completer.popup():
            self._constrain_completer_popup(obj)
        return super().eventFilter(obj, event)

    def _refresh_theme_style(self):
        """主题切换时刷新自身样式 + completer popup 样式"""
        # 防御：widget 可能已被销毁（C++ 对象已删除）
        import shiboken6
        if not shiboken6.isValid(self):
            return
        super()._refresh_theme_style()
        self._apply_completer_style()

    def _update_completer_model(self):
        """更新补全器的数据源"""
        model = QStringListModel(self._item_texts, self._search_completer)
        self._search_completer.setModel(model)

    def clear(self):
        """重写清空方法"""
        # 注意：qfluentwidgets 的 EditableComboBox.clear()
        # 内部可能只清空了菜单，我们也需要清空 LineEdit 内容和补全器
        super().clear()
        self._item_texts = []
        self._update_completer_model()
        self.setEditText("")

    def get_all_models(self):
        """获取当前模型列表中的所有模型名称"""
        models = []
        for i in range(self.count()):
            text = self.itemText(i)
            if text:
                models.append(text)
        return models

    def removeItemByText(self, text: str) -> bool:
        """按文本移除项"""
        idx = self.findText(text)
        if idx >= 0:
            self.removeItem(idx)
            return True
        return False

    def renameItem(self, old_text: str, new_text: str):
        """重命名项"""
        idx = self.findText(old_text)
        if idx >= 0:
            self.setItemText(idx, new_text)
            # 更新补全器
            if old_text in self._item_texts:
                idx_list = self._item_texts.index(old_text)
                self._item_texts[idx_list] = new_text
                self._update_completer_model()