from __future__ import annotations

import argparse
import logging
import os
import subprocess
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import mcp.types as types
from DrissionPage import Chromium, ChromiumOptions
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.lowlevel.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEVTOOLS_PROJECT = PROJECT_ROOT / "vendor" / "js-reverse-mcp"
DEFAULT_BROWSER_PATHS = [
    Path(
        os.environ.get(
            "DRISSIONPAGE_BROWSER_PATH",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        )
    ),
    Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
]

logger = logging.getLogger(__name__)


@dataclass
class LauncherConfig:
    port: int
    headless: bool
    browser_path: str | None
    user_data_dir: str | None
    chrome_args: list[str]
    devtools_project: Path
    node_bin: str
    npm_bin: str
    skip_build: bool
    forwarded_args: list[str]


@dataclass
class ProxyState:
    config: LauncherConfig
    browser: Chromium | None = None
    browser_url: str | None = None
    child_session: ClientSession | None = None
    child_tools: list[types.Tool] = field(default_factory=list)


def parse_args() -> LauncherConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Expose js-reverse-mcp as a single MCP server, but launch the browser "
            "through DrissionPage first."
        )
    )
    parser.add_argument("--port", type=int, default=9222, help="Remote debugging port.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Launch the browser in headless mode through DrissionPage.",
    )
    parser.add_argument(
        "--browser-path",
        help="Browser executable path used by DrissionPage. Defaults to Chrome on macOS if present.",
    )
    parser.add_argument(
        "--user-data-dir",
        help="Optional user data dir passed to DrissionPage.",
    )
    parser.add_argument(
        "--chrome-arg",
        action="append",
        default=[],
        help="Extra browser argument passed to DrissionPage. Can be repeated.",
    )
    parser.add_argument(
        "--devtools-project",
        default=str(DEFAULT_DEVTOOLS_PROJECT),
        help="Path to the local js-reverse-mcp project.",
    )
    parser.add_argument(
        "--node-bin",
        default=os.environ.get("DRISSIONPAGE_DEVTOOLS_NODE_BIN", "node"),
        help="Node executable used to start js-reverse-mcp.",
    )
    parser.add_argument(
        "--npm-bin",
        default=os.environ.get("DRISSIONPAGE_DEVTOOLS_NPM_BIN", "npm"),
        help="npm executable used when a build is needed.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Do not auto-build js-reverse-mcp when build output is missing.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level for the launcher.",
    )
    args, forwarded = parser.parse_known_args()
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    validate_forwarded_args(forwarded)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    return LauncherConfig(
        port=args.port,
        headless=args.headless,
        browser_path=resolve_browser_path(args.browser_path),
        user_data_dir=args.user_data_dir,
        chrome_args=args.chrome_arg,
        devtools_project=Path(args.devtools_project).expanduser(),
        node_bin=args.node_bin,
        npm_bin=args.npm_bin,
        skip_build=args.skip_build,
        forwarded_args=forwarded,
    )


def validate_forwarded_args(forwarded_args: list[str]) -> None:
    for arg in forwarded_args:
        if arg == "--browserUrl" or arg.startswith("--browserUrl="):
            raise SystemExit(
                "--browserUrl must not be passed through. The unified server sets it automatically."
            )
        if arg == "--wsEndpoint" or arg.startswith("--wsEndpoint="):
            raise SystemExit(
                "--wsEndpoint must not be passed through when using the DrissionPage-backed server."
            )


def resolve_browser_path(explicit_path: str | None) -> str | None:
    if explicit_path:
        return str(Path(explicit_path).expanduser())
    for candidate in DEFAULT_BROWSER_PATHS:
        if candidate.exists():
            return str(candidate)
    return None


def resolve_devtools_entry(config: LauncherConfig) -> Path:
    if not config.devtools_project.exists():
        raise RuntimeError(f"js-reverse-mcp project was not found: {config.devtools_project}")

    entry = config.devtools_project / "build" / "src" / "index.js"
    if entry.exists():
        return entry

    if config.skip_build:
        raise RuntimeError(
            f"js-reverse-mcp build output does not exist: {entry}. "
            "Re-run without --skip-build or build it manually."
        )

    logger.info("Building js-reverse-mcp because build/src/index.js is missing")
    subprocess.run([config.npm_bin, "run", "build"], cwd=config.devtools_project, check=True)

    if not entry.exists():
        raise RuntimeError(f"js-reverse-mcp build still missing after build: {entry}")
    return entry


def apply_chrome_args(options: ChromiumOptions, chrome_args: list[str]) -> None:
    for raw_arg in chrome_args:
        if not raw_arg:
            continue
        if "=" in raw_arg:
            name, value = raw_arg.split("=", 1)
            options.set_argument(name, value)
        else:
            options.set_argument(raw_arg)


def ensure_browser(config: LauncherConfig) -> tuple[Chromium, str]:
    options = ChromiumOptions(read_file=False)
    options.set_local_port(config.port)

    if config.browser_path:
        options.set_browser_path(config.browser_path)
    if config.headless:
        options.headless(True)
    if config.user_data_dir:
        options.set_user_data_path(Path(config.user_data_dir).expanduser())

    apply_chrome_args(options, config.chrome_args)

    browser = Chromium(options)
    _ = browser.latest_tab
    return browser, f"http://{browser.address}"


async def fetch_all_child_tools(session: ClientSession) -> list[types.Tool]:
    tools: list[types.Tool] = []
    cursor: str | None = None

    while True:
        result = await session.list_tools(cursor=cursor)
        tools.extend(result.tools)
        cursor = result.nextCursor
        if not cursor:
            break

    return tools


def build_child_command(config: LauncherConfig, browser_url: str, entry: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=config.node_bin,
        args=[
            str(entry),
            "--browserUrl",
            browser_url,
            *config.forwarded_args,
        ],
        cwd=config.devtools_project,
        env=os.environ.copy(),
    )


def make_server(state: ProxyState) -> Server:
    @asynccontextmanager
    async def lifespan(_: Server):
        async with AsyncExitStack() as stack:
            entry = resolve_devtools_entry(state.config)
            browser, browser_url = await anyio.to_thread.run_sync(ensure_browser, state.config)
            state.browser = browser
            state.browser_url = browser_url

            logger.info("Browser is ready at %s", browser_url)
            logger.info("Starting js-reverse-mcp via %s", entry)

            server_params = build_child_command(state.config, browser_url, entry)
            read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()

            state.child_session = session
            state.child_tools = await fetch_all_child_tools(session)
            logger.info("Loaded %d devtools tools from child MCP", len(state.child_tools))

            yield state

    server = Server(
        name="drissionpage-devtools",
        version="0.2.0",
        instructions="Chrome DevTools MCP backed by a browser launched through DrissionPage.",
        lifespan=lifespan,
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return state.child_tools

    async def call_tool_handler(req: types.CallToolRequest) -> types.ServerResult:
        if state.child_session is None:
            return server._make_error_result("Child devtools MCP session is not initialized.")

        try:
            result = await state.child_session.call_tool(
                req.params.name,
                arguments=req.params.arguments or {},
            )
            return types.ServerResult(
                types.CallToolResult(
                    content=list(result.content),
                    structuredContent=result.structuredContent,
                    isError=result.isError,
                )
            )
        except Exception as exc:
            return server._make_error_result(str(exc))

    server.request_handlers[types.CallToolRequest] = call_tool_handler
    return server


async def run_stdio_server(config: LauncherConfig) -> None:
    state = ProxyState(config=config)
    server = make_server(state)
    init_options = server.create_initialization_options(NotificationOptions())

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)


def main() -> None:
    config = parse_args()
    anyio.run(run_stdio_server, config)


if __name__ == "__main__":
    main()
