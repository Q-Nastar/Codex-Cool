from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    api_format: Literal["responses", "chat", "anthropic"] = "chat"
    models: dict[str, str] = Field(default_factory=dict)
    extra_headers: dict[str, str] = Field(default_factory=dict)
    extra_params: dict[str, Any] = Field(default_factory=dict)
    timeout: float = 120.0
    max_retries: int = 3
    enabled: bool = True
    priority: int = 0


class RouteRule(BaseModel):
    client_format: Literal["responses", "chat", "anthropic"] | None = None
    model_pattern: str | None = None
    provider: str


class ProxyConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8766
    providers: list[ProviderConfig] = Field(default_factory=list)
    routes: list[RouteRule] = Field(default_factory=list)
    default_provider: str = ""
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


DEFAULT_CONFIG_PATH = Path.home() / ".codex-cool" / "config.yaml"


def load_config(path: Path | None = None) -> ProxyConfig:
    path = path or DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return ProxyConfig(**data)
    return ProxyConfig()


def save_config(config: ProxyConfig, path: Path | None = None) -> None:
    path = path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config.model_dump(exclude_none=True), f, default_flow_style=False, allow_unicode=True)


def resolve_api_key(provider: ProviderConfig) -> str:
    if provider.api_key.startswith("env:"):
        env_var = provider.api_key[4:]
        return os.environ.get(env_var, "")
    return provider.api_key
