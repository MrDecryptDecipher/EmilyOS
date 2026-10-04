"""Optional file-backed agent run history."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from emily.agents.models import AgentRunRecord, AgentRunResult


class AgentHistoryStore:
    """Persists compact run records as JSON under a root directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def _path(self, run_id: str) -> Path:
        safe = run_id.replace("/", "_").replace("\\", "_")
        return self.root / f"{safe}.json"

    async def record(self, result: AgentRunResult, *, title: str) -> AgentRunRecord:
        run = AgentRunRecord(
            run_id=f"run_{uuid4().hex[:12]}",
            agent_id=result.agent_id,
            kind=result.kind,
            title=title,
            success=result.success,
            attempts=result.attempts,
            latency_ms=result.latency_ms,
            mission_id=str(result.metadata.get("mission_id")) if result.metadata.get("mission_id") else None,
            task_id=str(result.metadata.get("task_id")) if result.metadata.get("task_id") else None,
            verification=result.verification,
            error=result.error,
            output_preview=(result.output[:280] + ("..." if len(result.output) > 280 else "")),
        )
        path = self._path(run.run_id)
        payload = run.model_dump(mode="json")
        async with self._lock:
            await asyncio.to_thread(path.write_text, json.dumps(payload, indent=2), "utf-8")
        return run

    async def list_runs(self, *, limit: int = 50) -> list[AgentRunRecord]:
        files = sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        records: list[AgentRunRecord] = []
        for path in files[: max(0, limit)]:
            raw = await asyncio.to_thread(path.read_text, "utf-8")
            records.append(AgentRunRecord.model_validate(json.loads(raw)))
        return records

    async def clear(self) -> int:
        files = list(self.root.glob("*.json"))
        async with self._lock:
            for path in files:
                await asyncio.to_thread(path.unlink)
        return len(files)
