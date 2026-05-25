from __future__ import annotations

import json
import logging
import os
import time
import httpx
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from codex_cool.config import ProviderConfig, ProxyConfig, load_config, save_config

logger = logging.getLogger(__name__)

api_router = APIRouter(prefix="/api")

FRONTEND_DIR = Path(__file__).parent / "frontend"

PROVIDER_TEMPLATES = {
    "deepseek": {
        "name": "deepseek",
        "display_name": "DeepSeek",
        "description": "DeepSeek API - 高性价比大模型",
        "base_url": "https://api.deepseek.com/v1",
        "api_format": "chat",
        "models": {"deepseek-chat": "deepseek-chat", "deepseek-reasoner": "deepseek-reasoner"},
        "icon": "🧠",
        "color": "#4f46e5",
    },
    "openai": {
        "name": "openai",
        "display_name": "OpenAI",
        "description": "OpenAI GPT 系列模型",
        "base_url": "https://api.openai.com/v1",
        "api_format": "chat",
        "models": {"gpt-4o": "gpt-4o", "gpt-4o-mini": "gpt-4o-mini", "o1": "o1", "o3-mini": "o3-mini"},
        "icon": "🤖",
        "color": "#10a37f",
    },
    "anthropic": {
        "name": "anthropic",
        "display_name": "Anthropic",
        "description": "Claude 系列模型",
        "base_url": "https://api.anthropic.com/v1",
        "api_format": "anthropic",
        "models": {
            "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022",
        },
        "icon": "🎭",
        "color": "#d4a574",
    },
    "gemini": {
        "name": "gemini",
        "display_name": "Gemini",
        "description": "Google Gemini 系列模型",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_format": "chat",
        "models": {
            "gemini-2.5-pro": "gemini-2.5-pro",
            "gemini-2.5-flash": "gemini-2.5-flash",
            "gemini-2.0-flash": "gemini-2.0-flash",
        },
        "icon": "💎",
        "color": "#4285f4",
    },
    "kimi": {
        "name": "kimi",
        "display_name": "Kimi",
        "description": "月之暗面 - 长上下文模型",
        "base_url": "https://api.moonshot.cn/v1",
        "api_format": "chat",
        "models": {
            "moonshot-v1-8k": "moonshot-v1-8k",
            "moonshot-v1-32k": "moonshot-v1-32k",
            "moonshot-v1-128k": "moonshot-v1-128k",
        },
        "icon": "🌙",
        "color": "#6c5ce7",
    },
    "zhipu": {
        "name": "zhipu",
        "display_name": "智谱",
        "description": "智谱 AI - GLM 系列模型",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_format": "chat",
        "models": {
            "glm-4-plus": "glm-4-plus",
            "glm-4-flash": "glm-4-flash",
            "glm-4-long": "glm-4-long",
        },
        "icon": "🔮",
        "color": "#3742fa",
    },
    "qwen": {
        "name": "qwen",
        "display_name": "千问",
        "description": "阿里百炼 - 通义千问系列",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_format": "chat",
        "models": {
            "qwen-turbo": "qwen-turbo",
            "qwen-plus": "qwen-plus",
            "qwen-max": "qwen-max",
        },
        "icon": "☁️",
        "color": "#ff6348",
    },
    "doubao": {
        "name": "doubao",
        "display_name": "豆包",
        "description": "字节跳动 - Doubao 系列模型",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_format": "chat",
        "models": {},
        "icon": "🫘",
        "color": "#00b894",
    },
}


@api_router.get("/status")
async def get_status(request: Request):
    config: ProxyConfig = request.app.state.config
    router = request.app.state.router
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime = int(time.time() - start_time)

    providers_status = []
    for p in config.providers:
        cb = router.circuit_breakers.get(p.name)
        providers_status.append(
            {
                "name": p.name,
                "base_url": p.base_url,
                "api_format": p.api_format,
                "enabled": p.enabled,
                "circuit_breaker": cb.state if cb else "closed",
                "is_default": config.default_provider == p.name,
                "models": p.models,
                "has_api_key": bool(p.api_key),
            }
        )

    return {
        "running": True,
        "host": config.host,
        "port": config.port,
        "uptime": uptime,
        "providers": providers_status,
        "default_provider": config.default_provider,
        "log_level": config.log_level,
    }


@api_router.get("/providers")
async def list_providers(request: Request):
    config: ProxyConfig = request.app.state.config
    return [
        {
            "name": p.name,
            "base_url": p.base_url,
            "api_key_set": bool(p.api_key),
            "api_key_preview": (p.api_key[:8] + "..." if len(p.api_key) > 8 and not p.api_key.startswith("env:") else p.api_key) if p.api_key else "",
            "api_format": p.api_format,
            "models": p.models,
            "enabled": p.enabled,
            "priority": p.priority,
            "is_default": config.default_provider == p.name,
        }
        for p in config.providers
    ]


@api_router.post("/providers")
async def add_provider(request: Request):
    body = await request.json()
    config: ProxyConfig = request.app.state.config

    name = body.get("name", "").strip()
    if not name:
        return JSONResponse(content={"error": "Provider name is required"}, status_code=400)

    if any(p.name == name for p in config.providers):
        return JSONResponse(content={"error": f"Provider '{name}' already exists"}, status_code=409)

    provider = ProviderConfig(
        name=name,
        base_url=body.get("base_url", "").rstrip("/"),
        api_key=body.get("api_key", ""),
        api_format=body.get("api_format", "chat"),
        models=body.get("models", {}),
        enabled=body.get("enabled", True),
        priority=body.get("priority", 0),
    )
    config.providers.append(provider)

    if not config.default_provider:
        config.default_provider = name

    save_config(config)
    _refresh_router(request)

    return {"ok": True, "name": name}


@api_router.put("/providers/{name}")
async def update_provider(name: str, request: Request):
    body = await request.json()
    config: ProxyConfig = request.app.state.config

    provider = None
    for p in config.providers:
        if p.name == name:
            provider = p
            break

    if provider is None:
        return JSONResponse(content={"error": f"Provider '{name}' not found"}, status_code=404)

    if "base_url" in body:
        provider.base_url = body["base_url"].rstrip("/")
    if "api_key" in body:
        provider.api_key = body["api_key"]
    if "api_format" in body:
        provider.api_format = body["api_format"]
    if "models" in body:
        provider.models = body["models"]
    if "enabled" in body:
        provider.enabled = body["enabled"]
    if "priority" in body:
        provider.priority = body["priority"]

    save_config(config)
    _refresh_router(request)

    return {"ok": True}


@api_router.delete("/providers/{name}")
async def delete_provider(name: str, request: Request):
    config: ProxyConfig = request.app.state.config
    original_len = len(config.providers)
    config.providers = [p for p in config.providers if p.name != name]

    if len(config.providers) == original_len:
        return JSONResponse(content={"error": f"Provider '{name}' not found"}, status_code=404)

    if config.default_provider == name:
        config.default_provider = config.providers[0].name if config.providers else ""

    save_config(config)
    _refresh_router(request)

    return {"ok": True}


@api_router.post("/providers/{name}/test")
async def test_provider(name: str, request: Request):
    import httpx

    config: ProxyConfig = request.app.state.config
    provider = None
    for p in config.providers:
        if p.name == name:
            provider = p
            break

    if provider is None:
        return JSONResponse(content={"error": f"Provider '{name}' not found"}, status_code=404)

    from codex_cool.config import resolve_api_key

    api_key = resolve_api_key(provider)
    if not api_key:
        return JSONResponse(content={"error": "API key not configured"}, status_code=400)

    headers = {}
    if provider.api_format == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{provider.base_url.rstrip('/')}/models"
            resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                model_count = len(data.get("data", []))
                return {
                    "ok": True,
                    "status_code": resp.status_code,
                    "message": f"OK - {model_count} models available",
                }
            elif resp.status_code == 401:
                return {
                    "ok": False,
                    "status_code": resp.status_code,
                    "message": "Authentication failed - check API key",
                }
            elif resp.status_code == 404:
                chat_headers = {"Content-Type": "application/json", **headers}
                if provider.api_format == "anthropic":
                    chat_url = f"{provider.base_url.rstrip('/')}/messages"
                    payload = {
                        "model": list(provider.models.values())[0] if provider.models else "claude-sonnet-4-20250514",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    }
                else:
                    chat_url = f"{provider.base_url.rstrip('/')}/chat/completions"
                    payload = {
                        "model": list(provider.models.values())[0] if provider.models else "gpt-4o-mini",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    }
                resp = await client.post(chat_url, json=payload, headers=chat_headers)
                return {
                    "ok": resp.status_code < 500,
                    "status_code": resp.status_code,
                    "message": "OK" if resp.status_code < 400 else f"HTTP {resp.status_code}",
                }
            else:
                return {
                    "ok": resp.status_code < 500,
                    "status_code": resp.status_code,
                    "message": f"HTTP {resp.status_code}",
                }
    except httpx.ConnectError:
        return JSONResponse(content={"error": "Connection failed - check base URL"}, status_code=502)
    except httpx.TimeoutException:
        return JSONResponse(content={"error": "Connection timed out"}, status_code=504)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@api_router.post("/providers/{name}/models")
async def fetch_provider_models(name: str, request: Request):
    import httpx

    config: ProxyConfig = request.app.state.config
    provider = None
    for p in config.providers:
        if p.name == name:
            provider = p
            break

    if provider is None:
        return JSONResponse(content={"error": f"Provider '{name}' not found"}, status_code=404)

    from codex_cool.config import resolve_api_key

    api_key = resolve_api_key(provider)
    if not api_key:
        return JSONResponse(content={"error": "API key not configured"}, status_code=400)

    headers = {}
    if provider.api_format == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{provider.base_url.rstrip('/')}/models"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        model_ids = []
        for item in data.get("data", []):
            mid = item.get("id", "")
            if mid:
                model_ids.append(mid)
        model_ids.sort()

        return {"models": model_ids}
    except httpx.HTTPStatusError as e:
        return JSONResponse(content={"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}, status_code=502)
    except httpx.ConnectError:
        return JSONResponse(content={"error": "Connection failed - check base URL"}, status_code=502)
    except httpx.TimeoutException:
        return JSONResponse(content={"error": "Connection timed out"}, status_code=504)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)


@api_router.get("/config")
async def get_config(request: Request):
    config: ProxyConfig = request.app.state.config
    return {
        "host": config.host,
        "port": config.port,
        "log_level": config.log_level,
        "default_provider": config.default_provider,
        "cors_origins": config.cors_origins,
    }


@api_router.put("/config")
async def update_config(request: Request):
    body = await request.json()
    config: ProxyConfig = request.app.state.config

    if "host" in body:
        config.host = body["host"]
    if "port" in body:
        config.port = body["port"]
    if "log_level" in body:
        config.log_level = body["log_level"]
    if "default_provider" in body:
        config.default_provider = body["default_provider"]
    if "cors_origins" in body:
        config.cors_origins = body["cors_origins"]

    save_config(config)

    return {"ok": True, "restart_required": "port" in body or "host" in body}


@api_router.post("/fetch-models")
async def fetch_models(request: Request):
    body = await request.json()
    base_url = body.get("base_url", "").strip().rstrip("/")
    api_key = body.get("api_key", "").strip()
    api_format = body.get("api_format", "chat")
    provider_name = body.get("provider_name", "")

    if not base_url:
        return JSONResponse(content={"error": "base_url is required"}, status_code=400)

    if not api_key and provider_name:
        config: ProxyConfig = request.app.state.config
        for p in config.providers:
            if p.name == provider_name:
                from codex_cool.config import resolve_api_key
                api_key = resolve_api_key(p)
                break

    if api_key.startswith("env:"):
        env_var = api_key[4:]
        api_key = os.environ.get(env_var, "")

    headers = {}
    if api_key:
        if api_format == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

    models_url = f"{base_url}/models"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(models_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        model_ids = []
        for item in data.get("data", []):
            mid = item.get("id", "")
            if mid:
                model_ids.append(mid)
        model_ids.sort()

        return {"models": model_ids}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)


@api_router.get("/templates")
async def get_templates():
    return PROVIDER_TEMPLATES


@api_router.post("/providers/from-template")
async def add_from_template(request: Request):
    body = await request.json()
    template_name = body.get("template", "")
    api_key = body.get("api_key", "")

    template = PROVIDER_TEMPLATES.get(template_name)
    if not template:
        return JSONResponse(content={"error": f"Template '{template_name}' not found"}, status_code=404)

    config: ProxyConfig = request.app.state.config

    if any(p.name == template["name"] for p in config.providers):
        existing = next(p for p in config.providers if p.name == template["name"])
        if api_key:
            existing.api_key = api_key
        save_config(config)
        _refresh_router(request)
        return {"ok": True, "name": existing.name, "action": "updated"}

    provider = ProviderConfig(
        name=template["name"],
        base_url=template["base_url"],
        api_key=api_key,
        api_format=template["api_format"],
        models=template["models"],
        enabled=True,
        priority=0,
    )
    config.providers.append(provider)

    if not config.default_provider:
        config.default_provider = provider.name

    save_config(config)
    _refresh_router(request)

    return {"ok": True, "name": provider.name, "action": "created"}


@api_router.get("/inject/status")
async def get_inject_status():
    from codex_cool.injector import get_inject_status as _get_status
    return _get_status()


@api_router.post("/inject")
async def inject_codex(request: Request):
    body = await request.json()
    config: ProxyConfig = request.app.state.config

    model = body.get("model", "")
    api_key = body.get("api_key", "")

    if not model:
        default_provider = config.default_provider
        if default_provider:
            for p in config.providers:
                if p.name == default_provider and p.models:
                    model = list(p.models.keys())[0]
                    break
        if not model:
            model = "deepseek-chat"

    from codex_cool.injector import inject_codex_config
    result = inject_codex_config(
        proxy_host=config.host,
        proxy_port=config.port,
        model=model,
        api_key=api_key,
    )
    return result


@api_router.post("/uninject")
async def uninject_codex():
    from codex_cool.injector import uninject_codex_config
    return uninject_codex_config()


@api_router.get("/claude/inject/status")
async def get_claude_inject_status():
    from codex_cool.injector import get_claude_inject_status as _get_status
    return _get_status()


@api_router.post("/claude/inject")
async def inject_claude(request: Request):
    body = await request.json()
    config: ProxyConfig = request.app.state.config

    models = body.get("models", [])
    api_key = body.get("api_key", "")

    if not api_key:
        from codex_cool.config import resolve_api_key
        default_provider = config.default_provider
        if default_provider:
            for p in config.providers:
                if p.name == default_provider:
                    api_key = resolve_api_key(p)
                    break

    if not models:
        default_provider = config.default_provider
        if default_provider:
            for p in config.providers:
                if p.name == default_provider and p.models:
                    models = list(p.models.keys())[:3]
                    break
        if not models:
            models = ["claude-sonnet-4-20250514"]

    from codex_cool.injector import inject_claude_desktop, CLAUDE_MODEL_ALIASES
    result = inject_claude_desktop(
        proxy_host=config.host,
        proxy_port=config.port,
        api_key=api_key,
        models=models,
    )

    if result.get("ok"):
        _save_claude_alias_mappings(config, models, request)

    return result


def _save_claude_alias_mappings(config: ProxyConfig, selected_models: list[str], request: Request):
    from codex_cool.injector import CLAUDE_MODEL_ALIASES

    default_provider = config.default_provider
    provider = None
    for p in config.providers:
        if p.name == default_provider:
            provider = p
            break
    if not provider:
        return

    sorted_models = _sort_models_by_capability(selected_models)

    claude_aliases_by_capability = [
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-haiku-4-5-20251001",
    ]

    for i, alias in enumerate(claude_aliases_by_capability):
        if alias in provider.models:
            continue
        model_idx = min(i, len(sorted_models) - 1)
        provider.models[alias] = sorted_models[model_idx]

    save_config(config)
    _refresh_router(request)


def _sort_models_by_capability(models: list[str]) -> list[str]:
    high_keywords = ["opus", "pro", "max", "ultra", "o1", "o3"]
    low_keywords = ["haiku", "mini", "flash", "lite", "turbo", "small"]

    def score(m):
        m_lower = m.lower()
        for kw in high_keywords:
            if kw in m_lower:
                return -1
        for kw in low_keywords:
            if kw in m_lower:
                return 1
        return 0

    return sorted(models, key=score)


@api_router.post("/claude/uninject")
async def uninject_claude(request: Request):
    from codex_cool.injector import uninject_claude_desktop, CLAUDE_MODEL_ALIASES
    result = uninject_claude_desktop()

    if result.get("ok"):
        config: ProxyConfig = request.app.state.config
        for p in config.providers:
            for alias in CLAUDE_MODEL_ALIASES:
                p.models.pop(alias, None)
        save_config(config)
        _refresh_router(request)

    return result


@api_router.post("/reset-circuit-breaker/{name}")
async def reset_circuit_breaker(name: str, request: Request):
    router = request.app.state.router
    cb = router.circuit_breakers.get(name)
    if cb:
        cb.failure_count = 0
        cb.state = "closed"
        return {"ok": True}
    return JSONResponse(content={"error": f"Circuit breaker for '{name}' not found"}, status_code=404)


def _refresh_router(request: Request):
    config = load_config()
    request.app.state.config = config
    from codex_cool.proxy.router import ProxyRouter

    new_router = ProxyRouter(config)
    old_router = request.app.state.router
    request.app.state.router = new_router
    if old_router:
        import asyncio

        try:
            asyncio.get_event_loop().create_task(old_router.close())
        except Exception:
            pass
