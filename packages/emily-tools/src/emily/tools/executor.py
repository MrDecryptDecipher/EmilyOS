"""Tool executor with policy, timeout, and events."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from emily.tools.errors import ToolPermissionError, ToolPolicyError
from emily.tools.models import ToolInvocation, ToolResult
from emily.tools.policy import PermissionPolicy
from emily.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: PermissionPolicy | None = None,
        *,
        event_bus: Any | None = None,
        default_timeout_seconds: float = 15.0,
    ) -> None:
        self.registry = registry
        self.policy = policy or PermissionPolicy()
        self.event_bus = event_bus
        self.default_timeout_seconds = default_timeout_seconds

    async def invoke(self, invocation: ToolInvocation) -> ToolResult:
        started = time.perf_counter()
        tool = self.registry.get(invocation.tool_name)
        spec = tool.spec
        if not spec.enabled:
            result = ToolResult(
                tool_name=spec.name,
                success=False,
                denied=True,
                error="tool disabled",
                latency_ms=_latency(started),
            )
            await self._emit("tool.denied", result)
            return result

        try:
            used = self.policy.check(spec, capabilities=invocation.capabilities)
        except (ToolPolicyError, ToolPermissionError) as exc:
            result = ToolResult(
                tool_name=spec.name,
                success=False,
                denied=True,
                error=exc.message,
                latency_ms=_latency(started),
                permissions_used=list(spec.permissions),
            )
            await self._emit("tool.denied", result)
            return result

        timeout = (
            invocation.timeout_seconds
            if invocation.timeout_seconds is not None
            else self.default_timeout_seconds
        )
        try:
            output = await asyncio.wait_for(
                tool.handler(invocation.arguments),
                timeout=timeout,
            )
            result = ToolResult(
                tool_name=spec.name,
                success=True,
                output=dict(output),
                latency_ms=_latency(started),
                permissions_used=sorted(used, key=lambda p: p.value),
            )
            await self._emit("tool.invoked", result)
            return result
        except TimeoutError:
            result = ToolResult(
                tool_name=spec.name,
                success=False,
                error=f"tool timed out after {timeout}s",
                latency_ms=_latency(started),
                permissions_used=list(used),
            )
            await self._emit("tool.failed", result)
            return result
        except Exception as exc:
            result = ToolResult(
                tool_name=spec.name,
                success=False,
                error=str(exc),
                latency_ms=_latency(started),
                permissions_used=list(used),
            )
            await self._emit("tool.failed", result)
            return result

    async def _emit(self, event_type: str, result: ToolResult) -> None:
        if self.event_bus is None:
            return
        await self.event_bus.publish(
            event_type,
            {
                "tool_name": result.tool_name,
                "success": result.success,
                "denied": result.denied,
                "error": result.error,
                "latency_ms": result.latency_ms,
            },
            source="tools",
        )


def _latency(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
