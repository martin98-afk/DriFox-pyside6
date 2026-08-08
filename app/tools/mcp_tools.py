# -*- coding: utf-8 -*-
"""
MCP 工具模块 - 管理 MCP Server 连接、工具发现与调用

核心设计：
- MCPClientManager 是全局单例，多窗口共享连接池
- 所有 MCP 异步操作在一个专用后台线程的事件循环中执行
- 每个连接由一个持久 Task 管理，__aenter__/__aexit__ 在同一 Task 中
- 断开连接通过 Event 信号通知 Task 自然退出 async with 块
"""

import asyncio
import copy
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger
from mcp import types as mcp_types
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from app.tools.result import ToolResult


# ============================================================
# 状态机（供 UI 指示灯直接消费）
# ============================================================
class MCPState:
    """MCP 服务器连接状态（与 UI 指示灯颜色一一对应）

    DISABLED   → 黑色：用户关闭 / 未启动
    CONNECTING → 黄色：正在启动（进程拉起、握手、list_tools 全过程）
    CONNECTED  → 绿色：握手成功且工具已发现
    FAILED     → 红色：启动失败（超时 / 进程崩溃 / 协议错误）
    """

    DISABLED = "disabled"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"


# Windows 下单个环境变量值上限约 32767 字符（含结尾 \0）。超出时
# subprocess.Popen 会直接抛 ValueError，导致整个 stdio MCP 子进程创建失败。
# 宿主可能注入 ACC_PRODUCT_CONFIG_V3 等超大变量，必须丢弃。
_MAX_ENV_VALUE_LEN = 32766


def _build_stdio_env(env: Optional[dict]) -> dict:
    """构造 stdio 子进程环境变量。

    MCP SDK 默认只继承 DEFAULT_INHERITED_ENV_VARS（PATH/APPDATA 等十来个），
    会丢掉 HTTP_PROXY / HTTPS_PROXY / NODE_EXTRA_CA_CERTS / npm 镜像等关键变量，
    导致 npx / uvx 拉包失败 → 启动超时。这里显式继承完整父进程环境；
    但丢弃超长变量（见 _MAX_ENV_VALUE_LEN 说明）避免子进程创建失败。
    """
    merged = {}
    for k, v in os.environ.items():
        if not isinstance(v, str):
            continue
        # 跳过 bash 导出的函数定义（安全风险，SDK 同样过滤）
        if v.startswith("()"):
            continue
        # 跳过超长变量
        if len(v) > _MAX_ENV_VALUE_LEN:
            continue
        merged[k] = v
    if env:
        for k, v in env.items():
            if v is None:
                continue
            s = str(v)
            if len(s) <= _MAX_ENV_VALUE_LEN:
                merged[k] = s
    return merged


# ── 插件路径占位符兜底解析 ──────────────────────────────
def _expand_mcp_placeholder(value: str, plugin_root: Path) -> str:
    """将单个字符串中的 ${CLAUDE_PLUGIN_ROOT} / ${CLAUDE_PLUGIN_DATA} 解析为绝对路径。"""
    if not isinstance(value, str) or not value:
        return value
    root = plugin_root.as_posix()
    data = (plugin_root / "data").as_posix()
    normalized = value.replace("\\", "/")
    # 先替换长的（DATA 含 ROOT 前缀），避免 ${CLAUDE_PLUGIN_ROOT}/data 被部分替换
    return normalized.replace("${CLAUDE_PLUGIN_DATA}", data).replace("${CLAUDE_PLUGIN_ROOT}", root)


def _resolve_plugin_paths(config: dict) -> dict:
    """启动前兜底解析 config 中的插件路径占位符（防御旧缓存 / 热重载竞态 / UI 直增）。

    通过 config["_source"]（.mcp.json 路径）反推 plugin_root；无法反推时原样返回。
    """
    source = config.get("_source", "")
    plugin_root = None
    if source and source.endswith(".json"):
        p = Path(source)
        if p.parent.exists():
            plugin_root = p.parent
    if plugin_root is None:
        return config
    cfg = copy.deepcopy(config)
    cfg["command"] = _expand_mcp_placeholder(cfg.get("command", ""), plugin_root)
    cfg["args"] = [_expand_mcp_placeholder(a, plugin_root) for a in cfg.get("args", [])]
    cfg["url"] = _expand_mcp_placeholder(cfg.get("url", ""), plugin_root)
    cfg["env"] = {
        k: _expand_mcp_placeholder(v, plugin_root) if isinstance(v, str) else v
        for k, v in cfg.get("env", {}).items()
    }
    cfg["headers"] = {
        k: _expand_mcp_placeholder(v, plugin_root) if isinstance(v, str) else v
        for k, v in cfg.get("headers", {}).items()
    }
    return cfg


# ════════════════════════════════════════════════════════════════════════
# MCP stdio 子进程安全校验（DriFox-pyside6 同步自源项目 / AstrBot 设计）
# ════════════════════════════════════════════════════════════════════════
# 风险：MCP stdio 配置里的 `command` 会被直接 `subprocess.Popen`，没有校验等于
#       让 MCP 配置通道可以执行任意命令（curl|sh、rm、powershell 等）。
# 防御：四层校验：白名单 / 黑名单 / shell 元字符 / inline 代码标志。
#       任何一层失败 → 子进程不 spawn，返回 (False, error_msg)。

# 允许作为 MCP stdio launcher 的命令（不含扩展名，小写比较）
_STDIO_ALLOWED_COMMANDS = frozenset(
    {
        "python",
        "python3",
        "py",
        "node",
        "npx",
        "npm",
        "pnpm",
        "yarn",
        "bun",
        "bunx",
        "deno",
        "uv",
        "uvx",
    }
)

# 明确禁止的 stdio launcher（shell / 网络 / 危险文件操作 / 提权 / 关机类）
_STDIO_DENIED_COMMANDS = frozenset(
    {
        "bash",
        "sh",
        "zsh",
        "fish",
        "cmd",
        "cmd.exe",
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "osascript",
        "open",
        "curl",
        "wget",
        "nc",
        "netcat",
        "telnet",
        "ssh",
        "scp",
        "sftp",
        "rm",
        "mv",
        "cp",
        "dd",
        "mkfs",
        "sudo",
        "su",
        "chmod",
        "chown",
        "kill",
        "killall",
        "pkill",
        "shutdown",
        "reboot",
        "poweroff",
        "halt",
        "docker",
        "podman",
    }
)

# 命令中出现的 shell 元字符（包含即视为不可信——command 字段不应被解释为 shell）
_STDIO_SHELL_META_RE = re.compile(r"[\r\n\x00;&|<>\`$]")

# python -c / node -e 等 inline 代码标志
_STDIO_INLINE_PYTHON_FLAGS = frozenset({"-c"})  # 只禁 -c；-m 合法（模块启动）
_STDIO_INLINE_JS_FLAGS = frozenset({"-e", "--eval", "-p", "--print"})


def _normalize_stdio_command_name(command: str) -> str:
    """归一化命令名为小写裸名（去路径、去 Windows 扩展名）

    "C:\\Python312\\python.exe" → "python"
    "uvx" → "uvx"
    "npx.cmd" → "npx"
    """
    name = command.strip().replace("\\", "/")
    name = name.rsplit("/", 1)[-1]
    lower = name.lower()
    for ext in (".exe", ".cmd", ".bat", ".com", ".ps1"):
        if lower.endswith(ext):
            lower = lower[: -len(ext)]
    return lower


def _validate_stdio_config(config: dict) -> str:
    """校验 stdio 型 MCP 配置，返回空串=通过，非空串=拒绝原因。

    只对含 command 字段的配置做校验（stdio / http_from_stdio 都走子进程）；
    纯 url 型（sse/streamable http）不涉及本地子进程，直接放行。
    """
    command = config.get("command")
    if not command:
        return ""  # 无 command → 非 stdio（url 型），放行

    if not isinstance(command, str) or not command.strip():
        return "MCP stdio server 必须提供非空 command。"

    # 1) shell 元字符检查（command 字段本身不能被当成 shell 脚本执行）
    if _STDIO_SHELL_META_RE.search(command):
        return "MCP stdio command 含不安全的 shell 元字符（含 `;` `&` `|` `>` `$(` 等）。"

    cmd_name = _normalize_stdio_command_name(command)

    # 2) 危险命令黑名单
    if cmd_name in _STDIO_DENIED_COMMANDS:
        return f"MCP stdio command `{cmd_name}` 被安全策略禁止。"

    # 3) 白名单
    if cmd_name not in _STDIO_ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(_STDIO_ALLOWED_COMMANDS))
        return (
            f"MCP stdio command `{cmd_name}` 不在允许列表中。"
            f"允许的命令: {allowed}。建议改用 uvx / npx / python 等方式启动。"
        )

    # 4) args 校验：必须是字符串列表；控制字符 / inline 代码标志全拦
    args = config.get("args") or []
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return "MCP stdio args 必须为字符串列表。"

    for arg in args:
        if "\x00" in arg or "\r" in arg or "\n" in arg:
            return "MCP stdio args 不能包含控制字符（\\x00 / \\r / \\n）。"

    if cmd_name.startswith("python") or cmd_name == "py":
        if any(flag in args for flag in _STDIO_INLINE_PYTHON_FLAGS):
            return "MCP stdio Python server 禁止使用 `-c` inline 代码；应从模块或文件启动。"

    if cmd_name in {"node", "npx", "npm", "pnpm", "yarn", "bun", "bunx", "deno"}:
        if any(flag in args for flag in _STDIO_INLINE_JS_FLAGS):
            return "MCP stdio 禁止使用 inline eval 标志启动 server（应使用包或文件入口）。"

    return ""


def _extract_real_error(exc: Exception) -> Exception:
    """
    从嵌套的 ExceptionGroup/BaseExceptionGroup 中提取最底层的真实错误。
    如果无法提取，返回原异常。
    """
    # Python 3.11+ ExceptionGroup
    if hasattr(exc, "exceptions"):
        group = exc
        # 遍历所有层级，找到第一个非 ExceptionGroup 的异常
        while hasattr(group, "exceptions") and group.exceptions:
            for e in group.exceptions:
                if not hasattr(e, "exceptions") or not e.exceptions:
                    return e
            # 所有子异常都是 ExceptionGroup → 继续深入第一支
            group = group.exceptions[0]
    return exc


class MCPServerConnection:
    """单个 MCP Server 的连接管理"""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.tools: List[mcp_types.Tool] = []
        # 状态机（供 UI 指示灯直接消费）
        self.state: str = MCPState.CONNECTING
        self.last_error: str = ""
        self.updated_at: float = time.time()
        # 持久 Task 管理（__aenter__/__aexit__ 在同一 Task 中）
        self._task: Optional[asyncio.Task] = None
        self._disconnect_event: Optional[asyncio.Event] = None
        self._ready_event: Optional[asyncio.Event] = None
        self._connect_error: Optional[Exception] = None

    def set_state(self, state: str, error: str = "") -> None:
        self.state = state
        self.last_error = error
        self.updated_at = time.time()

    @property
    def server_type(self) -> str:
        return self.config.get("type", "stdio")

    @property
    def enabled(self) -> bool:
        return self.config.get("enabled", True)


class MCPClientManager:
    """
    MCP 客户端管理器（全局单例）

    所有异步 MCP 操作在专用后台线程的持久事件循环中执行。
    每个服务器连接由一个持久 asyncio.Task 管理：
    - Task 内部用 async with 持有 transport + session
    - 断开时设置 Event 信号，Task 自然退出 async with 块
    - 确保 __aenter__ / __aexit__ 在同一 Task 中执行
    """

    TOOL_PREFIX = "mcp__"

    _instance = None
    _ref_count = 0

    @classmethod
    def get_instance(cls) -> "MCPClientManager":
        if cls._instance is None:
            cls._instance = MCPClientManager()
        return cls._instance

    def __init__(self):
        if MCPClientManager._instance is not None and MCPClientManager._instance is not self:
            raise RuntimeError("请使用 MCPClientManager.get_instance() 获取单例")

        self._connections: Dict[str, MCPServerConnection] = {}
        self._connected = False
        # 全量连接去重：启动另一步全量时跳过（防多窗口连接踩踏）
        self._connect_all_running = False

        # 按 name 加锁：同一 server 只允许一个进行中的连接/断开操作
        self._busy_names: set = set()
        self._busy_lock = threading.Lock()

        # 专用后台线程 + 持久事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._start_loop()

    def _start_loop(self):
        """启动后台线程的持久事件循环"""
        self._loop_ready = threading.Event()

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, name="mcp-eventloop", daemon=True)
        self._thread.start()
        self._loop_ready.wait(timeout=5)
        logger.info("[MCP] 后台事件循环已启动")

    def _run_async(self, coro, timeout: float = 60):
        """在后台事件循环中执行协程，同步等待结果

        Args:
            coro: 协程对象
            timeout: 超时时间（秒），默认 60 秒

        Returns:
            协程执行结果

        Raises:
            TimeoutError: 执行超时
            RuntimeError: 事件循环未运行
        """
        if not self._loop or self._loop.is_closed():
            raise RuntimeError("MCP 事件循环未运行")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"协程执行超时（{timeout}秒）")
        except asyncio.CancelledError:
            # 🛡️ 透传取消信号，不拦截
            # 强制停止对话时 asyncio 会抛出 CancelledError（Python 3.11+ 是 BaseException），
            # 必须透传而非捕获，否则取消语义丢失并导致 Qt 事件循环收到未预期异常。
            raise
        except ExceptionGroup as e:
            # 处理 ExceptionGroup（Python 3.11+）
            raise _extract_real_error(e)
        except Exception as e:
            raise _extract_real_error(e)

    # ── 连接生命周期（持久 Task 模式）──────────────

    async def _server_lifespan(self, conn: MCPServerConnection) -> None:
        """
        连接生命周期 — 在专属 Task 中运行。

        用 async with 管理 transport 和 session，
        保证 __aenter__/__aexit__ 在同一 Task 中执行。
        断开时通过 _disconnect_event 信号自然退出。
        """
        server_type = conn.server_type
        try:
            if server_type == "stdio":
                await self._lifespan_stdio(conn)
            elif server_type == "sse":
                await self._lifespan_sse(conn)
            elif server_type == "http":
                # 如果 http 类型但含有 command 字段(无预设 URL)，需要先启动进程获取 URL
                if conn.config.get("command"):
                    await self._lifespan_http_from_stdio(conn)
                else:
                    await self._lifespan_http(conn)
            else:
                conn._connect_error = ValueError(f"不支持的 MCP 服务器类型: {server_type}")
                conn._ready_event.set()
        except asyncio.CancelledError:
            logger.debug(f"[MCP] 服务器 '{conn.name}' 的生命周期 Task 被取消")
        except Exception as e:
            if not conn._ready_event.is_set():
                # 尝试从 ExceptionGroup 中提取真实错误信息
                actual = _extract_real_error(e)
                conn._connect_error = actual
                conn._ready_event.set()
            else:
                logger.warning(f"[MCP] 服务器 '{conn.name}' 生命周期异常: {e}")
        finally:
            conn.session = None
            conn.tools = []
            logger.info(f"[MCP] 已断开服务器 '{conn.name}'")

    async def _lifespan_stdio(self, conn: MCPServerConnection) -> None:
        command = conn.config.get("command", "")
        args = conn.config.get("args", [])
        env = conn.config.get("env")

        # 纵深防御：_connect_single 已校验；此处再校验一次以防有人绕过入口
        reject = _validate_stdio_config(conn.config)
        if reject:
            raise ValueError(f"MCP stdio 安全校验失败: {reject}")

        params = StdioServerParameters(command=command, args=args, env=env)

        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                conn.session = session
                conn.tools = result.tools
                conn._ready_event.set()
                await conn._disconnect_event.wait()

    async def _lifespan_sse(self, conn: MCPServerConnection) -> None:
        url = conn.config.get("url", "")
        headers = conn.config.get("headers")

        async with sse_client(url=url, headers=headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                conn.session = session
                conn.tools = result.tools
                conn._ready_event.set()
                await conn._disconnect_event.wait()

    async def _lifespan_http(self, conn: MCPServerConnection) -> None:
        url = conn.config.get("url", "")
        headers = conn.config.get("headers")

        async with streamablehttp_client(url=url, headers=headers) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                conn.session = session
                conn.tools = result.tools
                conn._ready_event.set()
                await conn._disconnect_event.wait()

    async def _lifespan_http_from_stdio(self, conn: MCPServerConnection) -> None:
        """
        两阶段连接：先通过 stdio 启动服务器进程 -> 捕获 stdout 中的 URL -> 切换 HTTP 连接。

        适用场景：服务器使用 --transport http 参数，启动后输出 URL 到 stdout
        （如 @brave/brave-search-mcp-server --transport http）
        """
        command = conn.config.get("command", "")
        args = conn.config.get("args", [])
        command = conn.config.get("command", "")
        args = conn.config.get("args", [])
        env = conn.config.get("env")
        merged_env = {**os.environ, **(env or {})}

        # 纵深防御：与 _lifespan_stdio 一致，启动子进程前再校验一次
        # （_connect_single 已校验；此处防绕过入口的重复校验保持口径统一）
        reject = _validate_stdio_config(conn.config)
        if reject:
            raise ValueError(f"MCP stdio 安全校验失败: {reject}")

        logger.info(f"[MCP] '{conn.name}' 启动进程中获取 URL...")

        # 阶段一：启动进程并捕获 stdout（寻找 URL）
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

        found_url = None
        try:
            # 读取 stdout 寻找 URL（最大等待 15 秒）
            async def _find_url():
                nonlocal found_url
                assert process.stdout is not None
                url_pattern = re.compile(r'http[s]?://[^\s"\']+')
                while True:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=15)
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").strip()
                    logger.debug(f"[MCP] '{conn.name}' stdout: {decoded}")
                    # 尝试匹配 URL
                    match = url_pattern.search(decoded)
                    if match:
                        found_url = match.group(0)
                        return
                    # 也检查是否为纯 URL 行
                    if decoded.startswith("http://") or decoded.startswith("https://"):
                        found_url = decoded
                        return

            await _find_url()
        except asyncio.TimeoutError:
            # 超时未找到 URL，尝试杀掉进程后回退到 stdio
            try:
                process.kill()
            except Exception:
                pass
            raise TimeoutError(
                f"启动服务器 '{conn.name}' 后未能在 stdout 中找到 URL（15秒超时），"
                f"请确认服务器使用了正确的 --transport 参数"
            )

        if not found_url:
            try:
                process.kill()
            except Exception:
                pass
            raise RuntimeError(
                f"启动服务器 '{conn.name}' 后未能从输出中解析到 URL"
            )

        # 清理 URL 中的尾部分隔符
        found_url = found_url.rstrip("/,.;")
        # 如果 URL 是 0.0.0.0，替换为 localhost
        found_url = found_url.replace("0.0.0.0", "127.0.0.1")
        logger.info(f"[MCP] '{conn.name}' 获取到 URL: {found_url}")

        # 阶段二：用获取到的 URL 建立 HTTP 连接
        # 保持子进程运行（HTTP 服务器进程），连接关闭时杀掉进程
        try:
            async with streamablehttp_client(url=found_url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    conn.session = session
                    conn.tools = result.tools
                    conn._ready_event.set()
                    logger.info(f"[MCP] '{conn.name}' HTTP 连接成功，发现 {len(conn.tools)} 个工具")
                    await conn._disconnect_event.wait()
        finally:
            # 断开连接时杀掉子进程
            try:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
            except Exception:
                pass

    # ── 连接操作 ──────────────────────────────────────

    def connect_all_sync(self, servers_config: List[dict]) -> None:
        """同步连接所有 MCP 服务器（阻塞调用线程，慎用）"""
        self._run_async(self._connect_all(servers_config))

    def connect_all_background(self, servers_config: List[dict], on_done=None) -> None:
        """后台连接所有 MCP 服务器（不阻塞 UI 线程）

        多窗口场景下每个窗口都会调用一次，这里做全局去重：
        已有一轮全量连接在进行中时直接跳过，避免后启动的窗口把
        前一个窗口刚连好的连接全部断掉（连接踩踏）。
        """
        with self._busy_lock:
            if self._connect_all_running:
                logger.debug("[MCP] 已有全量连接进行中，跳过重复请求")
                if on_done:
                    try:
                        on_done(0, len(servers_config), [])
                    except Exception:
                        pass
                return
            self._connect_all_running = True

        def _worker():
            try:
                self._run_async(self._connect_all(servers_config), timeout=None)
            except Exception as e:
                logger.error(f"[MCP] 后台连接失败: {e}")
            finally:
                with self._busy_lock:
                    self._connect_all_running = False
                if on_done:
                    connected = sum(
                        1 for c in self._connections.values()
                        if c.state == MCPState.CONNECTED
                    )
                    failed = [
                        n for n, c in self._connections.items()
                        if c.state == MCPState.FAILED
                    ]
                    enabled_total = sum(1 for s in servers_config if s.get("enabled", True))
                    try:
                        on_done(connected, enabled_total, failed)
                    except Exception as e:
                        logger.warning(f"[MCP] on_done 回调异常: {e}")

        threading.Thread(target=_worker, name="mcp-connect", daemon=True).start()
        logger.info("[MCP] 后台连接已启动")

    async def _connect_all(self, servers_config: List[dict]) -> None:
        """全量同步到目标配置（增量，不做"先全断再全连"）

        原实现开头执行 _disconnect_all()，多窗口各调一次时会把已连好的
        连接反复拆掉重建，是"服务经常起不来"的主要来源之一。
        """
        # 收集需要连接的服务器列表
        enabled_servers = []
        enabled_names = set()
        for server_cfg in servers_config:
            name = server_cfg.get("name", "")
            if not name:
                continue
            if not server_cfg.get("enabled", True):
                continue
            enabled_servers.append(server_cfg)
            enabled_names.add(name)

        # 1) 断开已不在目标列表中的连接（配置被删除或被禁用）
        stale = [n for n, c in self._connections.items() if n not in enabled_names]
        for name in stale:
            try:
                await self._disconnect_single(name)
            except Exception as e:
                logger.warning(f"[MCP] 断开陈旧连接 '{name}' 失败: {e}")

        # 2) 跳过已连接且配置未变的 server（幂等，避免踩踏）
        pending = []
        for server_cfg in enabled_servers:
            name = server_cfg["name"]
            conn = self._connections.get(name)
            if conn and conn.state == MCPState.CONNECTED and conn.config == server_cfg:
                logger.debug(f"[MCP] '{name}' 已连接且配置未变，跳过")
                continue
            pending.append(server_cfg)

        if not pending:
            self._connected = any(
                c.state == MCPState.CONNECTED for c in self._connections.values()
            )
            return

        # 3) 并行启动所有待连接的服务器（不串行 await）
        tasks = {
            cfg["name"]: asyncio.create_task(
                self._connect_single(cfg["name"], cfg),
                name=f"mcp-connect-{cfg['name']}",
            )
            for cfg in pending
        }

        # 等待所有连接完成（每个任务内部各自超时，互不阻塞）
        for name, task in tasks.items():
            try:
                await task
            except Exception as e:
                logger.error(f"[MCP] 连接服务器 '{name}' 失败: {e}")

        # 从实际连接状态计算，避免全失败也显示已连接
        self._connected = any(
            c.state == MCPState.CONNECTED for c in self._connections.values()
        )

    def connect_server_sync(self, name: str, config: dict) -> bool:
        """同步连接单个 MCP 服务器（热添加）"""
        try:
            success, err = self._run_async(self._connect_single(name, config))
            if not success and err:
                logger.error(f"[MCP] 热添加服务器 '{name}' 失败: {err}")
            return success
        except Exception as e:
            logger.error(f"[MCP] 热添加服务器 '{name}' 失败: {e}")
            return False

    def connect_server_background(self, name: str, config: dict, on_done=None) -> None:
        """后台连接单个 MCP 服务器（不阻塞 UI）

        同一 name 只允许一个进行中的连接操作，重复请求被丢弃。
        """
        # 防重：同名服务器正在连接/断开中，跳过
        with self._busy_lock:
            if name in self._busy_names:
                logger.debug(f"[MCP] '{name}' 正在连接/断开中，跳过重复请求")
                if on_done:
                    try:
                        on_done(name, False, "服务器正在操作中，请稍后重试")
                    except Exception:
                        pass
                return
            self._busy_names.add(name)

        def _worker():
            success = False
            error_msg = ""
            try:
                success, error_msg = self._run_async(self._connect_single(name, config))
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[MCP] 热添加服务器 '{name}' 失败: {e}")
            finally:
                with self._busy_lock:
                    self._busy_names.discard(name)
                if on_done:
                    try:
                        on_done(name, success, error_msg)
                    except Exception as e:
                        logger.warning(f"[MCP] on_done 回调异常: {e}")

        threading.Thread(target=_worker, name="mcp-hot-add", daemon=True).start()

    async def _connect_single(self, name: str, config: dict) -> tuple:
        """
        连接单个服务器：启动生命周期 Task 并等待就绪
        返回: (success: bool, error_msg: str)
        """
        # ── stdio 安全校验：在 spawn 子进程之前拦截危险配置 ──
        # 只拦截含 command 的 stdio 型配置；url 型（sse/http）直接放行。
        if config.get("command"):
            reject = _validate_stdio_config(config)
            if reject:
                logger.warning(f"[MCP] 拒绝启动服务器 '{name}': {reject}")
                conn = MCPServerConnection(name, config)
                conn._connect_error = ValueError(reject)
                self._connections[name] = conn
                return False, reject

        # 如果已存在，先断开
        if name in self._connections:
            await self._disconnect_single(name)

        conn = MCPServerConnection(name, config)
        conn._disconnect_event = asyncio.Event()
        conn._ready_event = asyncio.Event()
        conn._connect_error = None

        # 在后台事件循环中启动生命周期 Task
        conn._task = asyncio.ensure_future(self._server_lifespan(conn), loop=self._loop)

        # 等待就绪或出错（最多 30 秒）
        try:
            await asyncio.wait_for(conn._ready_event.wait(), timeout=30)
        except asyncio.TimeoutError:
            conn._task.cancel()
            msg = f"连接服务器 '{name}' 超时（30秒）"
            logger.error(f"[MCP] {msg}")
            return False, msg

        if conn._connect_error:
            err = conn._connect_error
            # 尝试提取更友好的错误信息
            err_str = str(err)
            if "JSONRPC" in err_str and "Invalid JSON" in err_str:
                # 服务器 stdout 输出了非 JSON 内容 → 可能是 http/sse 服务器却用了 stdio 类型
                err_str += "（服务器输出了非 JSON 内容到 stdout，请检查配置类型是否正确）"
            msg = f"连接服务器 '{name}' 失败: {err_str}"
            logger.error(f"[MCP] {msg}")
            return False, msg

        self._connections[name] = conn
        self._connected = True
        logger.info(f"[MCP] 已连接服务器 '{name}'，发现 {len(conn.tools)} 个工具")
        return True, ""

    # ── 断开连接 ──────────────────────────────────────

    def disconnect_server_sync(self, name: str) -> bool:
        """同步断开单个 MCP 服务器（快，不等待 Task 清理）"""
        try:
            return self._run_async(self._disconnect_single(name))
        except Exception as e:
            logger.error(f"[MCP] 热断开服务器 '{name}' 失败: {e}")
            return False

    def disconnect_server_background(self, name: str, on_done=None) -> None:
        """后台断开单个 MCP 服务器（不阻塞 UI）

        与 connect_server_background 共享一个锁，同名请求丢弃。
        """
        with self._busy_lock:
            if name in self._busy_names:
                logger.debug(f"[MCP] '{name}' 正在连接/断开中，跳过重复请求")
                if on_done:
                    try:
                        on_done(name)
                    except Exception:
                        pass
                return
            self._busy_names.add(name)

        def _worker():
            try:
                self._run_async(self._disconnect_single(name))
            except Exception as e:
                logger.error(f"[MCP] 热断开服务器 '{name}' 失败: {e}")
            finally:
                with self._busy_lock:
                    self._busy_names.discard(name)
                if on_done:
                    try:
                        on_done(name)
                    except Exception as e:
                        logger.warning(f"[MCP] on_done 回调异常: {e}")

        threading.Thread(target=_worker, name="mcp-hot-disconnect", daemon=True).start()

    async def _disconnect_single(self, name: str, *, keep_record: bool = False) -> bool:
        """断开单个服务器

        Args:
            keep_record: True 时保留注册表条目（仅置为 DISABLED，UI 显示黑色"已关闭"）；
                False 时从注册表移除。
        """
        conn = self._connections.get(name) if keep_record else self._connections.pop(name, None)
        if not conn:
            return False
        if keep_record:
            conn.set_state(MCPState.DISABLED)
        else:
            self._connections.pop(name, None)

        # 通知生命周期 Task 退出（走 async with 正常清理路径）
        if conn._disconnect_event:
            conn._disconnect_event.set()

        # 取消 Task 作为备份（CancelledError 在 async with 内触发 __aexit__）
        task = conn._task
        if task and not task.done():
            task.cancel()
            # 等待 Task 完全退出，确保子进程释放资源（文件锁、端口等），
            # 避免热重载时旧进程未完全退出 → 新进程初始化失败。
            try:
                await asyncio.wait({task}, timeout=5)
            except Exception as e:
                logger.debug(f"[MCP] 等待 '{name}' 生命周期退出异常: {e}")

        # 立即清除引用（keep_record 时保留 state 但清 session/tools）
        conn.session = None
        conn.tools = []
        self._connected = any(
            c.state == MCPState.CONNECTED for c in self._connections.values()
        )
        return True

    def disconnect_all_sync(self) -> None:
        """同步断开所有连接（快，不等待 Task 清理）"""
        try:
            self._run_async(self._disconnect_all())
        except Exception as e:
            logger.warning(f"[MCP] 断开连接失败: {e}")

    def disconnect_all_background(self, on_done=None) -> None:
        """后台断开所有连接（不阻塞 UI）"""
        def _worker():
            try:
                self._run_async(self._disconnect_all())
            except Exception as e:
                logger.error(f"[MCP] 后台断开所有连接失败: {e}")
            finally:
                if on_done:
                    try:
                        on_done()
                    except Exception as e:
                        logger.warning(f"[MCP] on_done 回调异常: {e}")

        threading.Thread(target=_worker, name="mcp-disconnect-all", daemon=True).start()

    async def _disconnect_all(self) -> None:
        names = list(self._connections.keys())
        for name in names:
            try:
                await self._disconnect_single(name)
            except Exception as e:
                logger.error(f"[MCP] 断开服务器 '{name}' 失败: {e}")

        self._connections.clear()
        self._connected = False

    def disconnect_missing(self, valid_names: set) -> None:
        """断开所有不在 valid_names 中的已注册连接

        用于热重载后清理：插件被删除 / .mcp.json 中服务器被移除 / 被禁用时，
        对应的子进程不会自动退出，需要显式断开，否则残留进程继续运行。
        """
        orphans = [n for n in self._connections if n not in valid_names]
        if not orphans:
            return
        logger.info(f"[MCP] 热重载检测到 {len(orphans)} 个已失效连接，准备断开: {orphans}")
        for name in orphans:
            self.disconnect_server_background(name)

    # ── 工具 Schema ──────────────────────────────────

    def get_tool_schemas(self) -> List[Dict]:
        """获取所有 MCP 工具的 OpenAI function calling schema"""
        schemas = []
        for server_name, conn in self._connections.items():
            if not conn.session or not conn.enabled:
                continue
            for tool in conn.tools:
                prefixed_name = f"{self.TOOL_PREFIX}{server_name}__{tool.name}"
                schema = {
                    "type": "function",
                    "function": {
                        "name": prefixed_name,
                        "description": tool.description or f"MCP tool: {tool.name}",
                        "parameters": tool.inputSchema or {
                            "type": "object",
                            "properties": {},
                        },
                    },
                }
                schemas.append(schema)
        return schemas

    # ── 工具调用 ──────────────────────────────────────

    def call_tool_sync(self, prefixed_name: str, arguments: dict, timeout: float = 120) -> ToolResult:
        """同步调用 MCP 工具（供 ToolExecutor 调用）

        Args:
            prefixed_name: 带前缀的工具名（如 mcp__server__tool）
            arguments: 工具参数
            timeout: 超时时间（秒），默认 120 秒
        """
        try:
            return self._run_async(self._call_tool(prefixed_name, arguments), timeout=timeout)
        except TimeoutError as e:
            logger.error(f"[MCP] 调用工具 '{prefixed_name}' 超时（{timeout}s）: {e}")
            return ToolResult(False, error=f"MCP 工具调用超时（{timeout}秒），请稍后重试")
        except Exception as e:
            logger.error(f"[MCP] 调用工具 '{prefixed_name}' 失败: {e}")
            return ToolResult(False, error=f"MCP 工具调用失败: {e}")

    async def _call_tool(self, prefixed_name: str, arguments: dict) -> ToolResult:
        parsed = self._parse_tool_name(prefixed_name)
        if not parsed:
            return ToolResult(False, error=f"无效的 MCP 工具名: {prefixed_name}")

        server_name, tool_name = parsed
        conn = self._connections.get(server_name)
        if not conn or not conn.session:
            return ToolResult(False, error=f"MCP 服务器 '{server_name}' 未连接")

        try:
            result = await conn.session.call_tool(tool_name, arguments)

            text_parts = []
            for content in (result.content or []):
                if isinstance(content, mcp_types.TextContent):
                    text_parts.append(content.text)
                elif hasattr(content, "text"):
                    text_parts.append(str(content.text))

            output = "\n".join(text_parts) if text_parts else str(result)

            if result.isError:
                return ToolResult(False, error=output)

            return ToolResult(True, content=output)

        except Exception as e:
            logger.error(f"[MCP] 调用工具 '{prefixed_name}' 失败: {e}")
            return ToolResult(False, error=f"MCP 工具调用失败: {e}")

    # ── 辅助方法 ──────────────────────────────────────

    def _parse_tool_name(self, prefixed_name: str) -> Optional[tuple]:
        if not prefixed_name.startswith(self.TOOL_PREFIX):
            return None
        remainder = prefixed_name[len(self.TOOL_PREFIX):]
        if "__" not in remainder:
            return None
        server_name, tool_name = remainder.split("__", 1)
        return server_name, tool_name

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_status(self) -> List[Dict]:
        # 注意：返回的 tools 必须带 mcp__{server}__ 前缀，与 get_tool_schemas() 保持一致，
        # 避免 LLM 从 mcp_list_servers 看到裸名后误用导致调用失败。
        #
        # 返回注册表中的**全部** server（含 CONNECTING / FAILED / DISABLED），
        # 旧实现只返回连接成功的条目，导致 UI 永远读不到"启动中"和"失败"两种状态。
        status = []
        with self._busy_lock:
            busy_names = set(self._busy_names)
        for name, conn in self._connections.items():
            busy = name in busy_names or conn.state == MCPState.CONNECTING
            status.append({
                "name": name,
                "type": conn.server_type,
                "enabled": conn.enabled,
                "connected": conn.session is not None and conn.state == MCPState.CONNECTED,
                # busy 集合中的 server 即便记录是旧的 FAILED，也应报告为启动中
                "state": MCPState.CONNECTING if busy and conn.state != MCPState.CONNECTED else conn.state,
                "error": conn.last_error,
                "busy": busy,
                "tool_count": len(conn.tools),
                "tools": [
                    f"{self.TOOL_PREFIX}{name}__{t.name}" for t in conn.tools
                ],
            })
        return status

    # ── 引用计数（多窗口生命周期）──────────────────────

    def acquire(self):
        MCPClientManager._ref_count += 1
        logger.debug(f"[MCP] acquire, ref_count={MCPClientManager._ref_count}")

    def release(self):
        MCPClientManager._ref_count = max(0, MCPClientManager._ref_count - 1)
        logger.debug(f"[MCP] release, ref_count={MCPClientManager._ref_count}")
        if MCPClientManager._ref_count == 0 and self._connected:
            self.disconnect_all_sync()

    def shutdown(self):
        """彻底关闭后台事件循环（进程退出时调用）"""
        if self._connected:
            self.disconnect_all_sync()
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)


# ═══════════════════════════════════════════════════════════
# MCP Server 自动发现
# ═══════════════════════════════════════════════════════════
# 配置路径来源参考：
# - Claude Desktop: https://modelcontextprotocol.io/docs/getting-started/installation
# - Cursor: https://www.rapidevelopers.com/mcp-tutorial/how-to-configure-mcp-in-cursor-settings
# - Windsurf: https://deepwiki.com/hidao80/mcp-tutorial-1/3.3-windsurf-setup
# - Claude Code: https://docs.code.claude.com/mcp/setup/
# - VS Code (Cline/Continue): .vscode/mcp.json（项目级）
# ═══════════════════════════════════════════════════════════


def _discover_claude_desktop_servers() -> List[dict]:
    """
    扫描 Claude Desktop 配置，发现 MCP 服务器

    配置路径：
    - Windows: %APPDATA%/Claude/claude_desktop_config.json
    - macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
    - Linux:   ~/.config/Claude/claude_desktop_config.json

    配置格式：
    {
      "mcpServers": {
        "server-name": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
        }
      }
    }
    """
    servers = []
    config_paths = []

    if os.name == "nt" or os.environ.get("OS") == "Windows_NT":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            config_paths.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
    elif os.uname().sysname == "Darwin":
        config_paths.append(os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json"))
    else:
        config_paths.append(os.path.expanduser("~/.config/Claude/claude_desktop_config.json"))

    for config_path in config_paths:
        if not os.path.exists(config_path):
            continue

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            config = json.loads(content) if content.strip() else {}
        except (json.JSONDecodeError, IOError, OSError) as e:
            logger.debug(f"[MCP] 解析 Claude Desktop 配置失败 {config_path}: {e}")
            continue

        mcp_servers = config.get("mcpServers", {})
        for name, server_cfg in mcp_servers.items():
            if not isinstance(server_cfg, dict):
                continue

            command = server_cfg.get("command", "")
            args = server_cfg.get("args", [])
            if not command:
                continue

            servers.append({
                "name": name,
                "type": "stdio",
                "command": command,
                "args": args,
                "env": server_cfg.get("env"),
                "enabled": False,
                "_source": "claude_desktop",
                "_source_path": config_path,
            })
            logger.info(f"[MCP] 发现 Claude Desktop 服务器: {name}")

    return servers


def _discover_cursor_servers() -> List[dict]:
    """
    扫描 Cursor IDE 配置，发现 MCP 服务器

    配置路径（全局）：
    - Windows: %APPDATA%/Cursor/User/globalStorage/mcp-settings.json
    - macOS:   ~/Library/Application Support/Cursor/User/globalStorage/mcp-settings.json
    - Linux:   ~/.config/Cursor/User/globalStorage/mcp-settings.json

    配置格式：
    {
      "mcpServers": {
        "server-name": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem"]
        }
      }
    }

    注意：Cursor 还支持项目级 ~/.cursor/mcp.json（全局），
    但由于是用户 home 目录，与全局配置重复，这里只扫描 globalStorage。
    """
    servers = []
    config_paths = []

    if os.name == "nt" or os.environ.get("OS") == "Windows_NT":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            config_paths.append(os.path.join(appdata, "Cursor", "User", "globalStorage", "mcp-settings.json"))
    elif os.uname().sysname == "Darwin":
        config_paths.append(os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage/mcp-settings.json"))
    else:
        config_paths.append(os.path.expanduser("~/.config/Cursor/User/globalStorage/mcp-settings.json"))

    for config_path in config_paths:
        if not os.path.exists(config_path):
            continue

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            config = json.loads(content) if content.strip() else {}
        except (json.JSONDecodeError, IOError, OSError) as e:
            logger.debug(f"[MCP] 解析 Cursor 配置失败 {config_path}: {e}")
            continue

        mcp_servers = config.get("mcpServers", {})
        for name, server_cfg in mcp_servers.items():
            if not isinstance(server_cfg, dict):
                continue

            command = server_cfg.get("command", "")
            args = server_cfg.get("args", [])
            if not command:
                continue

            servers.append({
                "name": name,
                "type": "stdio",
                "command": command,
                "args": args,
                "env": server_cfg.get("env"),
                "enabled": False,
                "_source": "cursor",
                "_source_path": config_path,
            })
            logger.info(f"[MCP] 发现 Cursor MCP 服务器: {name}")

    return servers


def _merge_and_deduplicate(existing: List[dict], discovered: List[dict]) -> Tuple[List[dict], List[dict]]:
    """
    合并已有配置和自动发现的配置，去重

    去重规则（按 command + args 组合判断）：
    - 已有配置保留
    - 新发现的如果 command+args 与已有完全相同则跳过
    - 新发现的如果 name 相同但 command+args 不同，name 后面加后缀区分

    Returns:
        (merged_list, new_ones) — 合并后的完整列表 + 仅新发现的列表
    """
    # 已有的 command+args 组合
    existing_signatures = set()
    for s in existing:
        cmd = s.get("command", "")
        args = tuple(s.get("args", []) or [])
        if cmd:
            existing_signatures.add((cmd, args))

    new_ones = []
    for srv in discovered:
        cmd = srv.get("command", "")
        args = tuple(srv.get("args", []) or [])
        if cmd and (cmd, args) not in existing_signatures:
            new_ones.append(srv)
            existing_signatures.add((cmd, args))  # 防止多个新发现重复

    # name 冲突处理
    existing_names = {s.get("name", "") for s in existing}

    def unique_name(name: str, suffix: str) -> str:
        if name not in existing_names:
            return name
        base = name
        idx = 1
        while f"{base}{suffix}{idx}" in existing_names:
            idx += 1
        return f"{base}{suffix}{idx}"

    for srv in new_ones:
        srv["name"] = unique_name(srv["name"], "_copy")

    merged = list(existing) + new_ones
    return merged, new_ones


def discover_and_merge() -> Tuple[List[dict], List[dict]]:
    """
    自动发现所有已知来源的 MCP 服务器

    发现结果由 backend._discover_mcp_servers() 写入 user-custom 插件，
    不再直接修改 Settings.mcp_servers。

    Returns:
        (all_servers, newly_discovered) — 所有服务器（含已有的）+ 新发现的列表
    """
    from app.core.plugin_manager import PluginManager

    pm = PluginManager.get_instance()
    existing = pm.get_mcp_servers() if pm.is_initialized() else []

    all_discovered = []
    all_discovered.extend(_discover_claude_desktop_servers())
    all_discovered.extend(_discover_cursor_servers())

    merged, new_ones = _merge_and_deduplicate(existing, all_discovered)

    if new_ones:
        logger.info(f"[MCP] 自动发现 {len(new_ones)} 个新服务器")

    return merged, new_ones
