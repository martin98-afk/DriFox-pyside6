import os
import platform
import plistlib
import subprocess
import tempfile
import glob
import weakref

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import QWidget, QApplication, QProgressDialog, QMessageBox
from PySide6.QtGui import QDesktopServices

from app.utils.config import Settings
from app.utils.fluent_shim import InfoBar, InfoBarPosition
from app.utils.utils import AsyncUpdateChecker, DownloadThread


class UpdateChecker(QWidget):
    """优化后的更新检查器"""
    finished = Signal(object)  # 供外部监听检查结果
    error = Signal(str)  # 供外部监听错误
    _instance = None
    _initialized = False

    # —— Session 级节流：App 进程内只自动检查一次 ——
    # 类级别状态：即使 _instance 被重建（get_instance 的 parent 失效路径）也保留，
    # 避免多窗口/复制/分支窗口场景下反复打 GitHub API。
    _checked_in_session: bool = False
    _check_in_progress: bool = False
    # —— 更新通知防重复：用户已见过一次"发现新版本"提示后不再弹 QMessageBox ——
    _update_notified: bool = False

    def __new__(cls, parent=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, parent=None):
        # 必须先检查，避免重复初始化 QWidget
        if self._initialized:
            self._parent_ref = weakref.ref(parent) if parent else None
            return
        super().__init__(parent)
        self._initialized = True
        self._parent_ref = weakref.ref(parent) if parent else None
        self.cfg = Settings.get_instance()

        self.platform = self.cfg.patch_platform.value
        self.repo = self.cfg.github_repo
        self.token = self.cfg.github_token.value
        self.current_version = self.cfg.current_version

        self.progress_dialog = None
        self.download_thread = None
        self.installer_path = None

    @classmethod
    def get_instance(cls, parent=None):
        if cls._instance is not None:
            try:
                if cls._instance.parent() is not None or cls._instance._parent_ref is not None:
                    pass
            except Exception:
                cls._instance = None

        if cls._instance is None:
            cls._instance = cls(parent)
        elif parent is not None:
            cls._instance._parent_ref = weakref.ref(parent)

        return cls._instance

    def parent_widget(self):
        if self._parent_ref is not None:
            parent = self._parent_ref()
            if parent is not None:
                return parent
        return super().parent()

    def check_update(self, force: bool = False):
        """检查更新

        Args:
            force: True 时跳过 session 节流（手动按钮场景）。自动检查（窗口初始化）
                   传默认 False，每个 App 进程内只真正打一次 GitHub API。
        """
        parent = self.parent_widget()
        if parent is None:
            return

        if not force:
            if UpdateChecker._check_in_progress:
                logger.debug("[UpdateChecker] 检查进行中，跳过重复触发")
                return
            if UpdateChecker._checked_in_session:
                logger.debug("[UpdateChecker] 本次进程已检查过更新，跳过")
                return

        UpdateChecker._check_in_progress = True
        self.async_checker = AsyncUpdateChecker(self)
        self.async_checker.finished.connect(self._on_check_finished)
        self.async_checker.error.connect(self._on_check_error)
        self.async_checker.start()

    def _forward_error(self, msg):
        self.error.emit(msg)
        self._show_error_notification("检查更新失败", msg)

    def _on_check_finished(self, latest_release):
        UpdateChecker._check_in_progress = False
        UpdateChecker._checked_in_session = True
        self.finished.emit(latest_release)
        if latest_release:
            latest_version = latest_release.get("tag_name", "").lstrip("v")
            if self._compare_versions(latest_version, self.current_version) > 0:
                self._show_update_notification(latest_release)

    def _on_check_error(self, msg):
        # 错误也标记为已检查，避免 API 故障时后续每个窗口都重复打
        UpdateChecker._check_in_progress = False
        UpdateChecker._checked_in_session = True
        self.error.emit(msg)
        self._show_error_notification("检查更新失败", msg)

    def _show_update_notification(self, latest_release):
        """显示更新通知"""
        # 防重复：本次进程已展示过新版本提示（不论用户选立即更新/稍后/查看详情），
        # 不再弹 QMessageBox。否则在多窗口/复制窗口场景下，每个窗口都会触发一次。
        if UpdateChecker._update_notified:
            return
        UpdateChecker._update_notified = True

        latest_version = latest_release.get("tag_name", "未知")
        html_url = latest_release.get("html_url", "").strip()

        # 使用 QMessageBox 作为更新通知
        msg_box = QMessageBox(self.parent_widget() or self)
        msg_box.setWindowTitle("发现新版本")
        msg_box.setText(f"发现新版本 {latest_version}")
        msg_box.setInformativeText("是否立即更新？")

        update_btn = msg_box.addButton("立即更新", QMessageBox.ButtonRole.AcceptRole)
        view_btn = msg_box.addButton("查看详情", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("稍后", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() == update_btn:
            self._start_download(latest_release)
        elif msg_box.clickedButton() == view_btn and html_url:
            QDesktopServices.openUrl(QUrl(html_url))

    def _start_download(self, latest_release):
        update_url = None
        exe_name = f"Update_{latest_release['tag_name']}.exe"

        system = platform.system().lower()

        for asset in latest_release.get("assets", []) or []:
            asset_name = asset["name"].lower()
            if system == "darwin" and asset_name.endswith(".dmg"):
                update_url = asset["browser_download_url"]
                exe_name = asset["name"]
                break
            elif system == "windows" and asset_name.endswith(".exe"):
                update_url = asset["browser_download_url"]
                exe_name = asset["name"]
                break

        if not update_url:
            self._show_error_notification("未找到安装程序", "请前往 Release 手动下载")
            return

        self.installer_path = os.path.join(tempfile.gettempdir(), exe_name)

        self.progress_dialog = QProgressDialog(
            "正在下载新版本...", "取消", 0, 100, self.parent_widget() or self
        )
        self.progress_dialog.setWindowTitle("软件更新")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self._cancel_download)

        self.download_thread = DownloadThread(
            update_url, self.installer_path, self.token
        )
        self.download_thread.progress_signal.connect(self.progress_dialog.setValue)
        self.download_thread.finished_signal.connect(self._handle_download_finished)
        self.download_thread.error_signal.connect(self._handle_download_error)
        self.download_thread.start()

    def _handle_download_finished(self):
        if self.progress_dialog:
            self.progress_dialog.close()

        system = platform.system().lower()
        title = "下载完成"
        content = (
            "安装包已准备就绪，是否立即关闭程序并升级？"
            if system == "windows"
            else "新版本已下载，是否立即关闭程序并自动升级？"
        )

        reply = QMessageBox.question(
            self.parent_widget() or self,
            title, content,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_installer()

    def _run_installer(self):
        system = platform.system().lower()
        try:
            if system == "darwin":
                self._run_macos_upgrade()
            else:
                subprocess.Popen(
                    [self.installer_path],
                    shell=False,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.DETACHED_PROCESS,
                )

            QApplication.quit()
            os._exit(0)
        except Exception as e:
            self._show_error_notification("启动失败", str(e))

    def _run_macos_upgrade(self):
        result = subprocess.run(
            ["hdiutil", "attach", "-nobrowse", "-plist", self.installer_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"DMG 挂载失败: {result.stderr}")
        if not result.stdout.strip():
            raise RuntimeError("hdiutil 未输出挂载信息（stdout 为空）")

        plist_data = plistlib.loads(result.stdout.encode())
        mount_point = None
        for entity in plist_data.get("system-entities", []):
            mount_point = entity.get("mount-point")
            if mount_point:
                break

        if not mount_point:
            raise RuntimeError("无法找到 DMG 挂载点")

        app_bundles = glob.glob(os.path.join(mount_point, "*.app"))
        if not app_bundles:
            raise RuntimeError(f"DMG 挂载卷中未找到 .app: {mount_point}")

        src_app = app_bundles[0]
        dst_app = os.path.join("/Applications", os.path.basename(src_app))

        if os.path.exists(dst_app):
            subprocess.run(["rm", "-rf", dst_app], check=True)

        subprocess.run(["ditto", src_app, dst_app], check=True)
        subprocess.run(["hdiutil", "detach", "-quiet", mount_point], capture_output=True)

        try:
            os.remove(self.installer_path)
        except OSError:
            pass

        subprocess.Popen(["open", dst_app])

    def _cancel_download(self):
        if self.download_thread:
            self.download_thread.is_canceled = True
            self.download_thread = None

    def _handle_download_error(self, error_msg):
        if self.progress_dialog:
            self.progress_dialog.close()
        self._show_error_notification("下载失败", error_msg)

    def _show_error_notification(self, title, content):
        """显示错误通知 (使用 InfoBar 底部通知条)"""
        parent = self.parent_widget()
        if parent is not None:
            InfoBar.error(
                title, content,
                parent=parent,
                position=InfoBarPosition.BOTTOM,
                duration=5000,
            )

    def _compare_versions(self, v1, v2):
        import re

        def split_version(v):
            match = re.match(r"^v?([\d.]+)(.*)", v.strip().lower())
            if not match:
                return [], ""
            nums = [int(x) for x in match.group(1).split(".") if x]
            suffix = match.group(2)
            return nums, suffix

        try:
            p1_nums, p1_suffix = split_version(v1)
            p2_nums, p2_suffix = split_version(v2)

            if p1_nums != p2_nums:
                return (p1_nums > p2_nums) - (p1_nums < p2_nums)

            if not p1_suffix and p2_suffix:
                return 1
            if p1_suffix and not p2_suffix:
                return -1

            return (p1_suffix > p2_suffix) - (p1_suffix < p2_suffix)

        except Exception:
            return (v1 > v2) - (v1 < v2)
