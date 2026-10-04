"""Shared OpenAI-compatible Chat Completions client."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

import httpx

from emily.core.types.provider import ProviderStatus
from emily.providers.errors import ProviderInvocationError, ProviderUnavailableError
from emily.providers.models import ChatCompletion, CompletionUsage
from emily.providers.pricing import estimate_cost_usd


class OpenAICompatibleClient:
    """Async client for OpenAI-compatible `/chat/completions` endpoints."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._default_headers = dict(default_headers or {})
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._client is not None:
            return
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self._default_headers,
        }
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(
                connect=10.0,
                read=self.timeout_seconds,
                write=30.0,
                pool=10.0,
            ),
        )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise ProviderUnavailableError(
                "provider client not started",
                provider=self.name,
            )
        return self._client

    async def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> ChatCompletion:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra:
            payload.update(dict(extra))

        started = time.perf_counter()
        data = await self._request_json("POST", "/chat/completions", json_body=payload)
        latency_ms = (time.perf_counter() - started) * 1000.0

        choices = data.get("choices") or []
        if not choices:
            raise ProviderInvocationError(
                "provider returned no choices",
                provider=self.name,
                details={"response_keys": list(data.keys())},
            )
        message = choices[0].get("message") or {}
        content = str(message.get("content") or "")
        usage_raw = data.get("usage") or {}
        usage = CompletionUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
            total_tokens=int(usage_raw.get("total_tokens") or 0),
        )
        if usage.total_tokens == 0:
            usage = CompletionUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.prompt_tokens + usage.completion_tokens,
            )
        return ChatCompletion(
            provider=self.name,
            model=str(data.get("model") or self.model),
            content=content,
            finish_reason=choices[0].get("finish_reason"),
            usage=usage,
            latency_ms=latency_ms,
            estimated_cost_usd=estimate_cost_usd(
                self.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
            ),
            raw=data,
        )

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra:
            payload.update(dict(extra))

        client = self._require_client()
        attempt = 0
        stream_headers = {"Accept": "text/event-stream"}
        while True:
            try:
                async with client.stream(
                    "POST",
                    "/chat/completions",
                    json=payload,
                    headers=stream_headers,
                ) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        raise ProviderInvocationError(
                            f"stream HTTP {response.status_code}",
                            provider=self.name,
                            details={"body": body[:2000]},
                        )
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            return
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            yield str(piece)
                return
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise ProviderUnavailableError(
                        "stream transport failed",
                        provider=self.name,
                        cause=exc,
                    ) from exc

    async def probe_health(self) -> ProviderStatus:
        if not self.api_key:
            return ProviderStatus.UNAVAILABLE
        client = self._require_client()
        try:
            response = await client.get("/models")
            if response.status_code < 400:
                return ProviderStatus.HEALTHY
            # Some gateways do not expose /models; treat auth-like failures carefully.
            if response.status_code in {401, 403}:
                return ProviderStatus.UNAVAILABLE
            return ProviderStatus.DEGRADED
        except (httpx.TransportError, httpx.TimeoutException):
            return ProviderStatus.UNAVAILABLE

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = self._require_client()
        attempt = 0
        while True:
            try:
                response = await client.request(method, path, json=json_body)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise ProviderUnavailableError(
                        "provider transport failed",
                        provider=self.name,
                        cause=exc,
                    ) from exc
                continue

            if response.status_code >= 500:
                attempt += 1
                if attempt > self.max_retries:
                    raise ProviderUnavailableError(
                        f"provider server error HTTP {response.status_code}",
                        provider=self.name,
                        details={"body": response.text[:2000]},
                    )
                continue

            if response.status_code >= 400:
                raise ProviderInvocationError(
                    f"provider client error HTTP {response.status_code}",
                    provider=self.name,
                    details={"body": response.text[:2000]},
                )

            data = response.json()
            if not isinstance(data, dict):
                raise ProviderInvocationError(
                    "provider returned non-object JSON",
                    provider=self.name,
                )
            return data
