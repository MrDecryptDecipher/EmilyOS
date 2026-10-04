"""Master cross-subsystem integration test exercising all 18 Emily OS packages."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from emily.agents.subsystem import AgentsSubsystem
from emily.browser.subsystem import BrowserSubsystem
from emily.coding.subsystem import CodingSubsystem
from emily.config.settings import EmilySettings
from emily.desktop.subsystem import DesktopSubsystem
from emily.events.bus import InProcessEventBus
from emily.kernel.executive import ExecutiveKernel, HeartbeatSubsystem
from emily.kernel.orchestrator import DeepOrchestrationEngine
from emily.memory.subsystem import MemorySubsystem
from emily.missions.subsystem import MissionsSubsystem
from emily.plugins.subsystem import PluginSubsystem
from emily.providers.subsystem import ProvidersSubsystem
from emily.security.subsystem import SecuritySubsystem
from emily.tools.subsystem import ToolsSubsystem
from emily.trading.subsystem import TradingSubsystem
from emily.vision.subsystem import VisionSubsystem
from emily.voice.subsystem import VoiceSubsystem

pytestmark = pytest.mark.asyncio


async def test_full_master_orchestration_all_subsystems(tmp_path: Path) -> None:
    event_bus = InProcessEventBus()
    await event_bus.start()

    settings = EmilySettings(
        environment="test",
        log_level="ERROR",
        mission_llm_planner=False,
        nvidia_api_key=SecretStr("nv-test-key"),
        routesme_api_key=SecretStr("rm-test-key"),
        memory_directory=tmp_path / "memory",
        world_model_directory=tmp_path / "world",
        missions_directory=tmp_path / "missions",
        agent_history_directory=tmp_path / "agents",
        mcp_catalog_path=tmp_path / "catalog.json",
        voice_directory=tmp_path / "voice",
        voice_models_directory=tmp_path / "models",
        plugins_directory=tmp_path / "plugins",
        _env_file=None,
    )

    kernel = ExecutiveKernel(settings=settings)
    kernel.register(HeartbeatSubsystem())
    kernel.register(ProvidersSubsystem())
    kernel.register(SecuritySubsystem())
    kernel.register(MemorySubsystem(memory_dir=tmp_path / "memory", world_dir=tmp_path / "world"))
    kernel.register(ToolsSubsystem(mcp_catalog_path=tmp_path / "catalog.json"))
    kernel.register(DesktopSubsystem())
    kernel.register(BrowserSubsystem())
    kernel.register(VoiceSubsystem())
    kernel.register(VisionSubsystem())
    kernel.register(MissionsSubsystem(missions_dir=tmp_path / "missions"))
    kernel.register(AgentsSubsystem(history_dir=tmp_path / "agents"))
    kernel.register(PluginSubsystem(plugins_dir=tmp_path / "plugins"))
    kernel.register(CodingSubsystem())
    kernel.register(TradingSubsystem())

    ctx = await kernel.start()
    try:
        report = await kernel.health()
        assert report["healthy"] is True
        assert len(report["subsystems"]) == 14

        # Instantiating DeepOrchestrationEngine over full kernel context
        orchestrator = DeepOrchestrationEngine(ctx, kernel=kernel)
        result = await orchestrator.execute_master_workflow(
            goal="Enterprise master verification & security trade audit",
            enable_voice=False,
        )

        assert result["status"] == "success"
        assert result["total_phases"] == 8
        assert len(result["phases"]) == 8
        assert all(p["status"] == "success" for p in result["phases"])

        # Check phase details
        phase_names = [p["name"] for p in result["phases"]]
        assert "Security & Capability Scopes" in phase_names
        assert "Coding Workbench & AST Indexing" in phase_names
        assert "Trading Broker & Risk Enforcer" in phase_names
        assert "Vision OCR & GUI Grounding" in phase_names
        assert "Hybrid Memory & Knowledge Graph" in phase_names
        assert "LangGraph Missions & Agent Supervisor" in phase_names
        assert "Multilingual Voice & Bengali Personality" in phase_names
        assert "Observability, Audit & Telemetry" in phase_names

        # Check Bengali impress phrase details
        voice_phase = next(p for p in result["phases"] if "Voice" in p["name"])
        assert voice_phase["details"]["impress_phrase"] == "Maarbo Ekhaane, Laash Porbe Shoshaane"

    finally:
        await kernel.stop()
