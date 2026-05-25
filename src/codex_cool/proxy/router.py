from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from codex_cool.config import ProviderConfig, ProxyConfig, resolve_api_key

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "closed"

    def record_success(self):
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def is_available(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        return True


class ProxyRouter:
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.providers: dict[str, ProviderConfig] = {}
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self._client: httpx.AsyncClient | None = None

        for p in config.providers:
            if p.enabled:
                self.providers[p.name] = p
                self.circuit_breakers[p.name] = CircuitBreaker()

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0))
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def resolve_provider(self, client_format: str, model: str) -> list[ProviderConfig]:
        for route in self.config.routes:
            if route.client_format and route.client_format != client_format:
                continue
            if route.model_pattern:
                import re

                if not re.match(route.model_pattern, model):
                    continue
            if route.provider in self.providers:
                provider = self.providers[route.provider]
                if self.circuit_breakers[route.provider].is_available():
                    return [provider]

        default_name = self.config.default_provider
        if default_name and default_name in self.providers:
            if self.circuit_breakers[default_name].is_available():
                return [self.providers[default_name]]

        candidates = []
        for p in self.providers.values():
            if self.circuit_breakers[p.name].is_available():
                candidates.append(p)
        candidates.sort(key=lambda x: x.priority, reverse=True)
        return candidates

    def get_upstream_url(self, provider: ProviderConfig, client_format: str) -> str:
        base = provider.base_url.rstrip("/")
        if provider.api_format == "chat":
            return f"{base}/chat/completions"
        elif provider.api_format == "responses":
            return f"{base}/responses"
        elif provider.api_format == "anthropic":
            return f"{base}/messages"
        return f"{base}/chat/completions"

    def get_upstream_headers(
        self, provider: ProviderConfig, original_headers: dict[str, str]
    ) -> dict[str, str]:
        api_key = resolve_api_key(provider)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if provider.api_format == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
            if "anthropic-version" in original_headers:
                headers["anthropic-version"] = original_headers["anthropic-version"]
            if "anthropic-beta" in original_headers:
                headers["anthropic-beta"] = original_headers["anthropic-beta"]
        else:
            headers["Authorization"] = f"Bearer {api_key}"

        for k, v in provider.extra_headers.items():
            headers[k] = v

        return headers

    async def forward_request(
        self,
        provider: ProviderConfig,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        is_stream: bool = False,
    ) -> httpx.Response:
        client = await self.get_client()
        try:
            if is_stream:
                req = client.build_request("POST", url, json=payload, headers=headers)
                resp = await client.send(req, stream=True)
            else:
                resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code >= 500:
                self.circuit_breakers[provider.name].record_failure()
                if is_stream:
                    try:
                        await resp.aread()
                    except Exception:
                        pass
                    logger.error(f"Provider {provider.name} returned {resp.status_code} (stream)")
                else:
                    logger.error(f"Provider {provider.name} returned {resp.status_code}: {resp.text[:200]}")
            elif resp.status_code >= 400:
                if is_stream:
                    try:
                        await resp.aread()
                    except Exception:
                        pass
                    logger.warning(f"Provider {provider.name} returned {resp.status_code} (stream)")
                else:
                    logger.warning(f"Provider {provider.name} returned {resp.status_code}: {resp.text[:200]}")
            else:
                self.circuit_breakers[provider.name].record_success()

            return resp
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            self.circuit_breakers[provider.name].record_failure()
            logger.error(f"Provider {provider.name} connection error: {e}")
            raise

    async def forward_with_failover(
        self,
        client_format: str,
        model: str,
        payload: dict[str, Any],
        original_headers: dict[str, str],
        is_stream: bool = False,
    ) -> tuple[ProviderConfig, httpx.Response]:
        providers = self.resolve_provider(client_format, model)
        last_error = None

        for provider in providers:
            try:
                url = self.get_upstream_url(provider, client_format)
                headers = self.get_upstream_headers(provider, original_headers)
                resp = await self.forward_request(provider, url, headers, payload, is_stream)
                self.circuit_breakers[provider.name].record_success()
                return provider, resp
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider.name} failed, trying next: {e}")
                continue

        raise RuntimeError(f"All providers failed. Last error: {last_error}")
