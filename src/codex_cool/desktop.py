from __future__ import annotations

import logging
import os
import sys
import threading
import webview

from codex_cool.config import load_config

logger = logging.getLogger(__name__)


def _start_server(host: str, port: int, ready_event: threading.Event):
    import uvicorn
    from codex_cool.main import create_app

    config = load_config()
    config.host = host
    config.port = port

    app = create_app(config)

    class ReadyMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "lifespan":
                ready_event.set()
            await self.app(scope, receive, send)

    app_with_middleware = ReadyMiddleware(app)
    uvicorn.run(app_with_middleware, host=host, port=port, log_level="warning")


def run_desktop(host: str = "127.0.0.1", port: int = 18080):
    _ensure_env_vars()

    ready_event = threading.Event()

    server_thread = threading.Thread(
        target=_start_server,
        args=(host, port, ready_event),
        daemon=True,
    )
    server_thread.start()

    ready_event.wait(timeout=10)

    window = webview.create_window(
        "Codex Cool",
        f"http://{host}:{port}",
        width=1100,
        height=720,
        min_size=(800, 500),
        text_select=True,
    )

    webview.start(debug=False)
    sys.exit(0)


def _ensure_env_vars():
    config = load_config()
    for p in config.providers:
        if p.api_key and not p.api_key.startswith("env:"):
            env_name = f"CODEX_COOL_{p.name.upper().replace('-', '_')}_API_KEY"
            if env_name not in os.environ:
                os.environ[env_name] = p.api_key

    if "CODEX_COOL_API_KEY" not in os.environ:
        default = config.default_provider
        if default:
            for p in config.providers:
                if p.name == default and p.api_key and not p.api_key.startswith("env:"):
                    os.environ["CODEX_COOL_API_KEY"] = p.api_key
                    break


if __name__ == "__main__":
    run_desktop()
