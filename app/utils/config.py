# -*- coding: utf-8 -*-
"""
全局配置管理 - JSON 配置（替代原 qfluentwidgets QConfig）

使用单例模式管理全局配置，包括：
- LLM 模型配置（API URL、模型名称、认证方式）
- 界面配置（主题、字体）
- 用户偏好配置

配置持久化到 JSON 文件。
"""
import atexit
import orjson as json
import os
from copy import deepcopy
from enum import Enum
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from loguru import logger


class ConfigValidator:
    """配置验证器基类"""
    def correct(self, value):
        return value


class BoolValidator(ConfigValidator):
    def correct(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value) if value is not None else False


class RangeValidator(ConfigValidator):
    def __init__(self, min_val, max_val):
        self.min = min_val
        self.max = max_val

    def correct(self, value):
        if value is None:
            return self.min
        try:
            v = int(value) if isinstance(value, str) else value
            return max(self.min, min(self.max, v))
        except (TypeError, ValueError):
            return self.min


class OptionsValidator(ConfigValidator):
    def __init__(self, options):
        self._options = list(options)

    def correct(self, value):
        if value in self._options:
            return value
        return self._options[0] if self._options else value


class ConfigSerializer:
    """配置序列化器基类"""
    def serialize(self, value):
        return value

    def deserialize(self, value):
        return value


class ConfigItem:
    """配置项描述符

    替代 qfluentwidgets 的 ConfigItem，通过描述符协议支持:
        settings.llm_model.value   # 读取
        settings.llm_model.value = x  # 写入
    """

    def __init__(self, section, key, default, validator=None, serializer=None, restart=False):
        self.section = section
        self.key = key
        self.default = default
        self.validator = validator or ConfigValidator()
        self.serializer = serializer or ConfigSerializer()
        self.restart = restart
        self._name = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return _BoundConfigItem(self, obj)

    def __set__(self, obj, value):
        pass  # 通过 descriptor + _BoundConfigItem.value 写入


class OptionsConfigItem(ConfigItem):
    """可选值配置项"""
    pass


class RangeConfigItem(ConfigItem):
    """范围配置项"""
    pass


class _BoundConfigItem:
    """实例访问 ConfigItem 时返回的绑定包装

    提供 .value 属性来读写实例的配置值，同时暴露 .validator/.key/.section 等属性
    """

    def __init__(self, item, obj):
        self._item = item
        self._obj = obj

    @property
    def value(self):
        return self._obj._values.get(self._item._name, deepcopy(self._item.default))

    @value.setter
    def value(self, v):
        self._obj._values[self._item._name] = self._item.validator.correct(v)

    @property
    def valueChanged(self):
        """兼容 qfluentwidgets 的 valueChanged 信号"""
        return self._obj._sig_holder.valueChanged

    @property
    def validator(self):
        return self._item.validator

    @validator.setter
    def validator(self, v):
        self._item.validator = v

    @property
    def key(self):
        return self._item.key

    @property
    def section(self):
        return self._item.section

    @property
    def restart(self):
        return self._item.restart


class _AppRestartSignal:
    """占位信号，替代 qfluentwidgets 的 appRestartSignal"""
    def emit(self):
        pass


class QConfig:
    """轻量级 JSON 配置基类（替代 qfluentwidgets.QConfig）

    从 JSON 文件加载/保存配置，通过 ConfigItem 描述符自动序列化。
    """

    file = None

    def __init__(self):
        self._values = {}
        # 信号持有器（QObject 子类才能持有 Signal）
        self._sig_holder = type('_SigHolder', (QObject,), {
            'valueChanged': Signal()
        })()
        self._cfg = type('_Cfg', (), {
            'appRestartSig': _AppRestartSignal(),
            'themeMode': None,
            'themeChanged': _AppRestartSignal(),
            'themeColor': None,
            'themeColorChanged': _AppRestartSignal(),
        })()
        self.theme = None
        # 用各 ConfigItem 的默认值初始化
        for name in dir(self.__class__):
            item = getattr(self.__class__, name)
            if isinstance(item, ConfigItem):
                self._values[name] = deepcopy(item.default)

    def _get_config_items(self):
        """返回 {属性名: ConfigItem} 字典"""
        items = {}
        for name in dir(self.__class__):
            item = getattr(self.__class__, name)
            if isinstance(item, ConfigItem):
                items[name] = item
        return items

    def load(self, file=None):
        """从 JSON 文件加载配置"""
        file = file or self.file
        if file and Path(str(file)).exists():
            try:
                data = json.loads(Path(str(file)).read_bytes())
                self._apply_dict(data)
            except Exception:
                logger.exception("加载配置文件失败")

    def _apply_dict(self, data):
        """将 dict 数据应用到配置项"""
        items = self._get_config_items()
        for name, item in items.items():
            section_data = data.get(item.section, {})
            if item.key in section_data:
                raw_value = section_data[item.key]
                deserialized = item.serializer.deserialize(raw_value)
                try:
                    self._values[name] = item.validator.correct(deserialized)
                except Exception:
                    self._values[name] = deepcopy(item.default)

    def toDict(self):
        """序列化为 {section: {key: value}} 格式"""
        result = {}
        items = self._get_config_items()
        for name, item in items.items():
            if item.section not in result:
                result[item.section] = {}
            value = self._values.get(name, deepcopy(item.default))
            result[item.section][item.key] = item.serializer.serialize(value)
        return result

    def save(self, file=None):
        """保存配置到 JSON 文件"""
        file = file or self.file
        if file:
            p = Path(str(file))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(json.dumps(self.toDict(), option=json.OPT_INDENT_2))

    def set(self, item, value, save=False, copy=True):
        """设置配置项的值

        Parameters
        ----------
        item: _BoundConfigItem
            从实例访问的配置项（如 settings.llm_model）
        value: any
            新值
        save: bool
            是否立即保存到文件
        copy: bool
            是否深拷贝新值
        """
        try:
            item.value = deepcopy(value) if copy else value
        except Exception:
            item.value = value

        if save:
            self.save()

        if item.restart:
            self._cfg.appRestartSig.emit()

        if item is self._cfg.themeMode:
            self.theme = value
            self._cfg.themeChanged.emit(value)

        if item is self._cfg.themeColor:
            self._cfg.themeColorChanged.emit(value)


class PatchPlatform(Enum):
    GITHUB = "github"
    GITEE = "gitee"
    GITCODE = "gitcode"


class ListDictValidator(ConfigValidator):
    def correct(self, value):
        if isinstance(value, list):
            return value
        return []


class QuickComponentsSerializer(ConfigSerializer):
    def serialize(self, value):
        return value

    def deserialize(self, value):
        if isinstance(value, list):
            return value
        return []


class Settings(QConfig):
    _instance = None
    _closing_down = False
    _config_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def _set_closing_down(cls):
        cls._closing_down = True
        if cls._instance is not None:
            cls._instance._closing = True

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            from app.utils.utils import get_app_data_dir
            app_data_dir = get_app_data_dir()
            cls._instance.file = app_data_dir / "app.config"
            try:
                cls._extend_theme_validator_before_load()
                cls._instance.load()
                cls._config_loaded = True
                cls._migrate_saved_providers(cls._instance)
            except Exception:
                logger.exception("无法加载配置文件")
                cls._config_loaded = False
        return cls._instance

    @classmethod
    def _migrate_saved_providers(cls, instance):
        saved_providers = instance.llm_saved_providers.value
        if not saved_providers or not isinstance(saved_providers, dict):
            return

        from app.core.provider_profile import apply_provider_save

        new_saved_providers = {}
        old_to_new = {}

        for old_key, info in saved_providers.items():
            if not isinstance(info, dict):
                info = {}
            api_key = info.get("API_KEY", "")
            tmp_info = dict(info)
            tmp_info.pop("config_id", None)
            new_key = apply_provider_save(
                new_saved_providers, tmp_info, info.get("provider_name", old_key)
            )
            old_to_new[old_key] = new_key

        if new_saved_providers.keys() == saved_providers.keys() and all(
            isinstance(v, dict) and v.get("config_id") == k
            for k, v in new_saved_providers.items()
        ):
            return

        instance.llm_saved_providers.value = new_saved_providers
        selected = instance.llm_selected_model.value
        if selected and selected in old_to_new:
            instance.llm_selected_model.value = old_to_new[selected]
        instance.save()
        logger.info(
            f"已迁移 {len(saved_providers)} 个服务商配置到 apikey hash 格式 "
            f"（合并后 {len(new_saved_providers)} 条）"
        )

    @classmethod
    def _extend_theme_validator_before_load(cls):
        try:
            from app.utils.theme_manager import theme_manager
            themes = list(theme_manager.list_themes().keys())
            if not themes:
                return

            if cls._instance.file and Path(str(cls._instance.file)).exists():
                try:
                    raw = Path(str(cls._instance.file)).read_text(encoding="utf-8")
                    data = json.loads(raw)
                    saved_theme = data.get("UI", {}).get("ThemeStyle")
                    if saved_theme and saved_theme not in themes:
                        themes.append(saved_theme)
                except Exception:
                    pass

            cls._instance.ui_theme_style.validator.__init__(themes)
        except Exception as e:
            import logging
            logging.warning(f"[_extend_theme_validator_before_load] failed: {e}")

    @classmethod
    def save_config(cls):
        instance = cls.get_instance()
        instance.save()

    def save(self):
        if Settings._closing_down:
            return
        if getattr(self, '_closing', False):
            return
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.closingDown():
                return
        except Exception:
            pass
        self.file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file, "wb") as f:
            f.write(json.dumps(self.toDict(), option=json.OPT_INDENT_2))

    # 开机自启
    auto_start = ConfigItem("General", "AutoStart", False, BoolValidator())

    # 版本信息
    current_version = "v0.2.6"
    auto_check_update = ConfigItem("General", "AutoCheckUpdate", True, BoolValidator())

    # 版本管理设置
    patch_platform = ConfigItem(
        "Patch",
        "Platform",
        "github",
        OptionsValidator([p.value for p in PatchPlatform]),
    )

    # GitHub 配置
    github_repo = "martin98-afk/DriFox"
    github_token = ConfigItem("Patch", "GitHub/Token", "")

    # ========== 大模型对话默认配置 ==========
    llm_model = ConfigItem("LLM", "Model", "qwen/qwen3-30b-a3b-2507")
    llm_api_key = ConfigItem("LLM", "APIKey", "")
    llm_api_base = ConfigItem("LLM", "APIBase", "http://127.0.0.1:1234/v1")
    llm_max_tokens = ConfigItem("LLM", "MaxTokens", 2048, RangeValidator(1024, 400960))
    llm_temperature = ConfigItem("LLM", "Temperature", 0.7, RangeValidator(0, 1))
    llm_saved_providers = ConfigItem("LLM", "SavedProviders", {})
    llm_model_overrides = ConfigItem("LLM", "ModelOverrides", {})
    llm_selected_model = ConfigItem("LLM", "SelectedModel", "")
    llm_subagent_default_model = ConfigItem("LLM", "SubagentDefaultModel", "")
    llm_enabled_skills = ConfigItem("LLM", "EnabledSkills", [
        "brainstorming", "writing-plans", "find-skills", "skill-creator", "git-commit", "minimax-image-understanding"
    ])
    llm_notify_enabled = ConfigItem("LLM", "NotifyEnabled", True, BoolValidator())
    llm_desktop_automation_enabled = ConfigItem(
        "LLM", "DesktopAutomationEnabled", True, BoolValidator()
    )
    llm_notify_sound = OptionsConfigItem(
        "LLM", "NotifySound", "beep",
        OptionsValidator(["beep", "short", "none"]),
    )
    llm_font_family = ConfigItem("LLM", "FontFamily", "Segoe UI")

    # ========== UI appearance ==========
    ui_font_size = OptionsConfigItem(
        "UI", "FontSize", "medium",
        OptionsValidator(["small", "medium", "large", "superlarge"]),
    )
    ui_theme_style = OptionsConfigItem(
        "UI", "ThemeStyle", "fallout",
        OptionsValidator(["fallout"]),
    )

    # ========== 会话项目管理 ==========
    current_project = ConfigItem("Session", "CurrentProject", "默认项目")

    # ========== LLM API 服务配置 ==========
    llm_api_enabled = ConfigItem("LLM", "APIEnabled", False, BoolValidator())
    llm_api_port = RangeConfigItem("LLM", "APIPort", 8765, RangeValidator(1024, 65535))

    # ========== MCP 服务器配置 ==========
    mcp_servers = ConfigItem("MCP", "Servers", [], ListDictValidator())
    mcp_enabled = ConfigItem("MCP", "Enabled", True, BoolValidator())
    mcp_discovered = ConfigItem("MCP", "Discovered", False, BoolValidator())

    # ========== 插件系统配置 ==========
    enabled_plugins = ConfigItem("Plugin", "EnabledPlugins", [])

    # ========== 云组件库API ==========
    SERPAPI_KEY = ConfigItem(
        "CloudAPI", "SerpAPI",
        "42e2b2817bf48352d3caa227212ebb82d6f8839cdd39b304c68cf58b42961c27",
    )

    # ========== Gateway 通讯平台配置 ==========
    gateway_wecom_enabled = ConfigItem("Gateway", "WeCom/Enabled", False, BoolValidator())
    gateway_wecom_bot_id = ConfigItem("Gateway", "WeCom/BotID", "")
    gateway_wecom_secret = ConfigItem("Gateway", "WeCom/Secret", "")
    gateway_wecom_websocket_url = ConfigItem("Gateway", "WeCom/WebSocketURL", "wss://openws.work.weixin.qq.com")

    gateway_dingtalk_enabled = ConfigItem("Gateway", "DingTalk/Enabled", False, BoolValidator())
    gateway_dingtalk_client_id = ConfigItem("Gateway", "DingTalk/ClientID", "")
    gateway_dingtalk_client_secret = ConfigItem("Gateway", "DingTalk/ClientSecret", "")

    gateway_telegram_enabled = ConfigItem("Gateway", "Telegram/Enabled", False, BoolValidator())
    gateway_telegram_token = ConfigItem("Gateway", "Telegram/Token", "")
    gateway_telegram_require_mention = ConfigItem("Gateway", "Telegram/RequireMention", True, BoolValidator())

    gateway_discord_enabled = ConfigItem("Gateway", "Discord/Enabled", False, BoolValidator())
    gateway_discord_token = ConfigItem("Gateway", "Discord/Token", "")
    gateway_discord_require_mention = ConfigItem("Gateway", "Discord/RequireMention", True, BoolValidator())

    gateway_whatsapp_enabled = ConfigItem("Gateway", "WhatsApp/Enabled", False, BoolValidator())
    gateway_whatsapp_account_sid = ConfigItem("Gateway", "WhatsApp/AccountSID", "")
    gateway_whatsapp_auth_token = ConfigItem("Gateway", "WhatsApp/AuthToken", "")
    gateway_whatsapp_from_number = ConfigItem("Gateway", "WhatsApp/FromNumber", "")

    gateway_feishu_enabled = ConfigItem("Gateway", "Feishu/Enabled", False, BoolValidator())
    gateway_feishu_app_id = ConfigItem("Gateway", "Feishu/AppID", "")
    gateway_feishu_app_secret = ConfigItem("Gateway", "Feishu/AppSecret", "")

    gateway_slack_enabled = ConfigItem("Gateway", "Slack/Enabled", False, BoolValidator())
    gateway_slack_bot_token = ConfigItem("Gateway", "Slack/BotToken", "")
    gateway_slack_app_token = ConfigItem("Gateway", "Slack/AppToken", "")

    # ========== Gitee 图床配置 ==========
    gitee_enabled = ConfigItem("Gitee", "Enabled", True, BoolValidator())
    gitee_token = ConfigItem("Gitee", "Token", "a5dcb6e2e7776143b7a7e7685a1f33a3")
    gitee_owner = ConfigItem("Gitee", "Owner", "dingmama123141")
    gitee_repo = ConfigItem("Gitee", "Repo", "canvas-mind-components")
    gitee_path = ConfigItem("Gitee", "Path", "drifox")
    gitee_branch = ConfigItem("Gitee", "Branch", "master")

    # ========== LSP 配置 ==========
    lsp_auto_diagnose = ConfigItem("LSP", "AutoDiagnose", False, BoolValidator())

    # ========== 工具开关控制 ==========
    tool_toggles = ConfigItem("Tools", "Toggles", {})
    tool_off_behavior = ConfigItem("Tools", "OffBehavior", "deny")


def update_theme_options():
    """从 ThemeManager 动态更新主题选项验证器"""
    try:
        from app.utils.theme_manager import theme_manager
        themes = list(theme_manager.list_themes().keys())
        if themes:
            settings = Settings.get_instance()
            settings.ui_theme_style.validator.__init__(themes)
            if settings.ui_theme_style.value not in themes:
                settings.ui_theme_style.value = themes[0]
    except Exception as e:
        import logging
        logging.warning(f"[update_theme_options] failed: {e}")

atexit.register(Settings._set_closing_down)
