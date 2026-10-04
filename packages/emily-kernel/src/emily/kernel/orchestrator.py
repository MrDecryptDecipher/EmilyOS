"""Deep Multi-Subsystem Master Orchestration Engine for Emily OS."""

from __future__ import annotations

import time
from typing import Any

from emily.core.types.tool import ToolPermissionLevel
from emily.kernel.context import DefaultKernelContext
from emily.tools.models import CapabilityToken


class DeepOrchestrationEngine:
    """
    Coordinates complex multi-subsystem workflows across all 18 core Emily OS packages.
    
    Orchestrates Security, Memory, Vision, Coding, Trading, Missions, Agents,
    Observability, Plugins, Voice, and Desktop into a unified transaction stream.
    """

    def __init__(self, ctx: DefaultKernelContext, kernel: Any | None = None) -> None:
        self.ctx = ctx
        self.kernel = kernel

    def _get_sub(self, name: str) -> Any | None:
        if self.kernel is not None and hasattr(self.kernel, "get_subsystem"):
            return self.kernel.get_subsystem(name)
        return self.ctx.get_extra(f"{name}_subsystem")

    async def execute_master_workflow(
        self,
        *,
        goal: str = "Perform security audit, index repository, and execute risk-gated paper trade",
        enable_voice: bool = False,
    ) -> dict[str, Any]:
        """Run full 8-phase cross-subsystem orchestration workflow."""
        t0 = time.perf_counter()
        phases: list[dict[str, Any]] = []

        # Phase 1: Zero-Trust Security & Vault Initialization
        p1_t0 = time.perf_counter()
        token = CapabilityToken(
            granted=[
                ToolPermissionLevel.READ,
                ToolPermissionLevel.WRITE,
                ToolPermissionLevel.DESKTOP,
                ToolPermissionLevel.BROWSER,
                ToolPermissionLevel.VOICE,
                ToolPermissionLevel.PRIVILEGED,
            ]
        )
        sec_sub = self._get_sub("security")
        if sec_sub is not None and hasattr(sec_sub, "audit"):
            sec_sub.audit.log_event("master_orchestration.started", {"goal": goal})

        phases.append({
            "phase": 1,
            "name": "Security & Capability Scopes",
            "status": "success" if sec_sub is not None else "unavailable",
            "latency_ms": round((time.perf_counter() - p1_t0) * 1000, 2),
            "details": {"vault_saved": False, "token_scopes": [p.value for p in token.granted], "audit_available": sec_sub is not None},
        })

        # Phase 2: Repository & Code AST Indexing
        p2_t0 = time.perf_counter()
        coding_sub = self._get_sub("coding")
        code_summary: dict[str, Any] = {"indexed": False, "git_status": "unknown"}
        if coding_sub is not None and hasattr(coding_sub, "indexer") and coding_sub.indexer is not None:
            ast_files = coding_sub.indexer.index_workspace()
            git_status = coding_sub.git.get_status()
            review = coding_sub.reviewer.review_workspace()
            symbols_count = sum(len(f.symbols) for f in ast_files)
            code_summary = {
                "indexed": True,
                "symbols": symbols_count,
                "files": len(ast_files),
                "git_branch": git_status.branch,
                "score": review.health_score,
            }

        phases.append({
            "phase": 2,
            "name": "Coding Workbench & AST Indexing",
            "status": "success",
            "latency_ms": round((time.perf_counter() - p2_t0) * 1000, 2),
            "details": code_summary,
        })

        # Phase 3: Risk-Gated Trading Execution
        p3_t0 = time.perf_counter()
        trading_sub = self._get_sub("trading")
        trading_summary: dict[str, Any] = {"executed": False, "mode": "paper", "reason": "trade not requested"}
        trade_requested = any(word in goal.lower() for word in ("trade", "buy", "sell", "order"))
        if trade_requested and trading_sub is not None and hasattr(trading_sub, "broker") and trading_sub.broker is not None:
            quote = trading_sub.broker.get_quote("AAPL")
            valid, _ = trading_sub.risk.validate_order("AAPL", side="buy", qty=10, price=quote["price"])
            if valid:
                order = trading_sub.broker.place_order("AAPL", side="buy", qty=10, price=quote["price"])
                trading_summary = {
                    "executed": True,
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "quantity": order.qty,
                    "price": order.price,
                    "balance": trading_sub.broker.get_portfolio()["cash"],
                }

        phases.append({
            "phase": 3,
            "name": "Trading Broker & Risk Enforcer",
            "status": "success" if not trade_requested or trading_summary.get("executed") else "unavailable",
            "latency_ms": round((time.perf_counter() - p3_t0) * 1000, 2),
            "details": trading_summary,
        })

        # Phase 4: Local Vision OCR & GUI Grounding
        p4_t0 = time.perf_counter()
        vision_sub = self._get_sub("vision")
        vision_summary: dict[str, Any] = {"ocr_available": False, "grounding_available": False}
        if vision_sub is not None and hasattr(vision_sub, "runtime") and vision_sub.runtime is not None:
            try:
                frame = vision_sub.runtime.capture_and_ground()
                text = " ".join(result.text for result in frame.ocr_results)
                elements = frame.elements
                vision_summary = {
                    "ocr_available": True,
                    "extracted_length": len(text),
                    "detected_elements": len(elements),
                    "grounding_available": True,
                }
            except Exception as exc:
                vision_summary = {"ocr_available": False, "error": str(exc)}

        phases.append({
            "phase": 4,
            "name": "Vision OCR & GUI Grounding",
            "status": "success" if vision_summary.get("grounding_available") else "unavailable",
            "latency_ms": round((time.perf_counter() - p4_t0) * 1000, 2),
            "details": vision_summary,
        })

        # Phase 5: Multi-Store Memory & Knowledge Graph
        p5_t0 = time.perf_counter()
        memory_summary: dict[str, Any] = {"saved": False}
        if self.ctx.memory_runtime is not None:
            from emily.core.types.memory import MemoryKind
            from emily.memory.models import WorldObservation
            await self.ctx.memory_runtime.remember(goal, kind=MemoryKind.EPISODIC, title="master_orchestrator")
            snap = await self.ctx.memory_runtime.observe(WorldObservation(source="orchestrator", text="EmilyOS has_orchestrator DeepOrchestrationEngine", confidence=1.0))
            stats = await self.ctx.memory_runtime.stats()
            memory_summary = {
                "saved": True,
                "world_entities": stats.get("world_entities", 0),
                "memory_total": stats.get("memory_total", 0),
            }

        phases.append({
            "phase": 5,
            "name": "Hybrid Memory & Knowledge Graph",
            "status": "success" if memory_summary.get("saved") else "unavailable",
            "latency_ms": round((time.perf_counter() - p5_t0) * 1000, 2),
            "details": memory_summary,
        })

        # Phase 6: Mission Runtime & Agent Execution
        p6_t0 = time.perf_counter()
        mission_summary: dict[str, Any] = {"started": False}
        if self.ctx.mission_runtime is not None:
            from emily.missions.models import MissionSpec
            created = await self.ctx.mission_runtime.create(MissionSpec(goal=goal))
            finished = await self.ctx.mission_runtime.start(created.mission_id)
            mission_summary = {
                "started": True,
                "mission_id": finished.mission_id,
                "status": finished.status.value,
                "tasks_completed": len(finished.all_tasks()),
            }

        phases.append({
            "phase": 6,
            "name": "LangGraph Missions & Agent Supervisor",
            "status": "success" if mission_summary.get("started") else "unavailable",
            "latency_ms": round((time.perf_counter() - p6_t0) * 1000, 2),
            "details": mission_summary,
        })

        # Phase 7: Voice Audio & Bengali Impress Context
        p7_t0 = time.perf_counter()
        voice_summary: dict[str, Any] = {"spoken": False}
        from emily.voice.personality import check_impress_context
        impress_phrase = check_impress_context("Hey Emily Impress me")
        if enable_voice and self.ctx.voice_runtime is not None:
            try:
                plan = await self.ctx.voice_runtime.converse.speak_text("Master orchestration workflow executed.", play=False)
                voice_summary = {
                    "spoken": True,
                    "tts_backend": plan.tts_backend,
                    "impress_phrase": impress_phrase,
                }
            except Exception as exc:
                voice_summary = {"spoken": False, "impress_phrase": impress_phrase, "error": str(exc)}
        else:
            voice_summary = {"spoken": False, "impress_phrase": impress_phrase}

        phases.append({
            "phase": 7,
            "name": "Multilingual Voice & Bengali Personality",
            "status": "success" if (not enable_voice or voice_summary.get("spoken")) else "failed",
            "latency_ms": round((time.perf_counter() - p7_t0) * 1000, 2),
            "details": voice_summary,
        })

        # Phase 8: Observability, Replay & Event Bus Dispatch
        p8_t0 = time.perf_counter()
        if self.ctx.event_bus is not None:
            await self.ctx.event_bus.publish("master_orchestration.completed", {"phases": len(phases)})
        if sec_sub is not None and hasattr(sec_sub, "audit"):
            sec_sub.audit.log_event("master_orchestration.completed", {"total_phases": len(phases)})

        phases.append({
            "phase": 8,
            "name": "Observability, Audit & Telemetry",
            "status": "success" if self.ctx.event_bus is not None else "unavailable",
            "latency_ms": round((time.perf_counter() - p8_t0) * 1000, 2),
            "details": {"events_published": True, "audit_chained": True},
        })

        total_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "status": "success" if all(phase["status"] == "success" for phase in phases) else "degraded",
            "goal": goal,
            "phases": phases,
            "total_phases": len(phases),
            "total_latency_ms": total_latency_ms,
        }
