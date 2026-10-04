"""Small, side-effect-free helpers for the local Workbench boundary."""

from __future__ import annotations

from urllib.parse import urlparse


MAX_CHAT_LENGTH = 16_000
MAX_COMMAND_LENGTH = 8_000
MAX_SEARCH_LENGTH = 512


def bounded_text(value: object, *, name: str, maximum: int) -> str:
    text = str(value or "").strip()
    if len(text) > maximum:
        raise ValueError(f"{name} exceeds the {maximum} character limit")
    return text


def is_local_origin(origin: str | None) -> bool:
    """Allow browser clients served locally, while rejecting ambient websites."""
    if not origin:
        return True
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def runtime_capabilities(*, kernel: object | None, vision: object, desktop: object, browser: object) -> dict[str, bool]:
    ctx = getattr(kernel, "_ctx", None)
    return {
        "kernel": bool(kernel and getattr(kernel, "_started", False)),
        "providers": bool(ctx and getattr(ctx, "provider_router", None)),
        "vision": vision is not None,
        "desktop": desktop is not None,
        "browser": browser is not None,
        "memory": bool(ctx and getattr(ctx, "memory_runtime", None)),
    }
