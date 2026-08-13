"""Register voice actions as tools."""

from __future__ import annotations

from typing import Any

from emily.core.types.tool import ToolPermissionLevel
from emily.tools.models import ToolSource, ToolSpec
from emily.tools.registry import ToolRegistry
from emily.voice.runtime import VoiceRuntime

# Prefer VOICE permission level (added in emily-core); fall back noted for older cores.
_VOICE_PERM = getattr(ToolPermissionLevel, "VOICE", ToolPermissionLevel.EXECUTE)


def register_voice_tools(registry: ToolRegistry, runtime: VoiceRuntime) -> list[str]:
    """Register voice tools; returns registered tool names."""

    names: list[str] = []

    async def speak(args: dict[str, Any]) -> dict[str, Any]:
        plan = await runtime.speak(str(args.get("text", "")), play=bool(args.get("play", True)))
        return plan.model_dump(mode="json")

    async def listen(args: dict[str, Any]) -> dict[str, Any]:
        transcript = await runtime.listen_once(duration_s=float(args.get("duration_s", 3.0)))
        return {"transcript": transcript}

    async def status(_args: dict[str, Any]) -> dict[str, Any]:
        return (await runtime.status()).model_dump(mode="json")

    async def barge_in(_args: dict[str, Any]) -> dict[str, Any]:
        return await runtime.barge_in()

    async def models(args: dict[str, Any]) -> dict[str, Any]:
        name = args.get("name")
        return {"models": runtime.model_status(str(name) if name else None)}

    specs: list[tuple[ToolSpec, Any]] = [
        (
            ToolSpec(
                name="voice.speak",
                title="Voice Speak",
                description="Speak text via the local TTS stack",
                permissions=[_VOICE_PERM],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "play": {"type": "boolean"},
                    },
                    "required": ["text"],
                },
                metadata={"subsystem": "voice"},
            ),
            speak,
        ),
        (
            ToolSpec(
                name="voice.listen",
                title="Voice Listen",
                description="Capture microphone audio and transcribe once",
                permissions=[_VOICE_PERM],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {"duration_s": {"type": "number"}},
                },
                metadata={"subsystem": "voice"},
            ),
            listen,
        ),
        (
            ToolSpec(
                name="voice.status",
                title="Voice Status",
                description="Voice runtime status, backends, and metrics",
                permissions=[ToolPermissionLevel.READ, _VOICE_PERM],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "voice"},
            ),
            status,
        ),
        (
            ToolSpec(
                name="voice.barge_in",
                title="Voice Barge-In",
                description="Interrupt current speech / generation",
                permissions=[_VOICE_PERM],
                source=ToolSource.PLUGIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "voice"},
            ),
            barge_in,
        ),
        (
            ToolSpec(
                name="voice.models",
                title="Voice Models",
                description="List local voice model status (no silent downloads)",
                permissions=[ToolPermissionLevel.READ, _VOICE_PERM],
                source=ToolSource.PLUGIN,
                input_schema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
                metadata={"subsystem": "voice"},
            ),
            models,
        ),
    ]

    for spec, handler in specs:
        registry.register(spec, handler)
        names.append(spec.name)
    return names
