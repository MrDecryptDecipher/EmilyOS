"""RoutesMe OpenAI-compatible adapter factory."""

from __future__ import annotations

from emily.providers.adapter import OpenAICompatibleProvider
from emily.providers.openai_compat import OpenAICompatibleClient


def create_routesme_provider(
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout_seconds: float = 120.0,
    max_retries: int = 2,
) -> OpenAICompatibleProvider:
    client = OpenAICompatibleClient(
        name="routesme",
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )
    return OpenAICompatibleProvider(client)
