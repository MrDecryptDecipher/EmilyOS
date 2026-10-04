"""Concurrency gate for agent execution."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from emily.agents.errors import AgentCapacityError


class AgentPool:
    """Limits how many agents may run work concurrently."""

    def __init__(self, max_concurrent: int = 8) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self.max_concurrent = max_concurrent
        self._sema = asyncio.Semaphore(max_concurrent)
        self._active = 0
        self._lock = asyncio.Lock()
        self._waiters = 0

    @property
    def active(self) -> int:
        return self._active

    @property
    def waiters(self) -> int:
        return self._waiters

    def snapshot(self) -> dict[str, int]:
        return {
            "max_concurrent": self.max_concurrent,
            "active": self._active,
            "waiters": self._waiters,
            "available": self.max_concurrent - self._active,
        }

    @asynccontextmanager
    async def acquire(self, *, wait_timeout: float | None = None) -> AsyncIterator[None]:
        async with self._lock:
            self._waiters += 1
        try:
            if wait_timeout is None:
                await self._sema.acquire()
            else:
                try:
                    await asyncio.wait_for(self._sema.acquire(), timeout=wait_timeout)
                except TimeoutError as exc:
                    raise AgentCapacityError(
                        f"agent pool saturated (max={self.max_concurrent})",
                        details=self.snapshot(),
                    ) from exc
        finally:
            async with self._lock:
                self._waiters = max(0, self._waiters - 1)

        async with self._lock:
            self._active += 1
        try:
            yield
        finally:
            async with self._lock:
                self._active = max(0, self._active - 1)
            self._sema.release()
