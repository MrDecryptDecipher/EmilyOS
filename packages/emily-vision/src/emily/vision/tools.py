"""Register vision actions as tools into Emily ToolRegistry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from emily.core.types.tool import ToolPermissionLevel
from emily.tools.models import ToolSource, ToolSpec
from emily.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from emily.vision.runtime import VisionRuntime


def register_vision_tools(registry: ToolRegistry, runtime: VisionRuntime) -> list[str]:
    """Register vision tools into Emily ToolRegistry; returns tool names."""

    names: list[str] = []

    async def capture_screen(_args: dict[str, Any]) -> dict[str, Any]:
        frame = runtime.capture_and_ground()
        return frame.to_dict()

    async def find_element(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", ""))
        frame = runtime.last_frame or runtime.capture_and_ground()
        element = runtime.grounding_engine.locate_element_by_label(frame, query)
        if element:
            return element.to_dict()
        return {"found": False, "query": query}

    async def look_around(_args: dict[str, Any]) -> dict[str, Any]:
        frame_bytes = runtime.capture_webcam()
        if not frame_bytes:
            return {"error": "Could not access webcam."}
        return runtime.analyze_objects(frame_bytes)

    async def read_emotions(_args: dict[str, Any]) -> dict[str, Any]:
        frame_bytes = runtime.capture_webcam()
        if not frame_bytes:
            return {"error": "Could not access webcam."}
        return runtime.analyze_emotions(frame_bytes)

    specs: list[tuple[ToolSpec, Any]] = [
        (
            ToolSpec(
                name="vision_look_around",
                title="Look Around Room",
                description="Use the webcam to detect objects and people in the physical environment.",
                permissions=[ToolPermissionLevel.READ],
                source=ToolSource.BUILTIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "vision"},
            ),
            look_around,
        ),
        (
            ToolSpec(
                name="vision_read_emotions",
                title="Read Emotions",
                description="Use the webcam to deeply analyze the user's facial expression, emotions, and characteristics.",
                permissions=[ToolPermissionLevel.READ],
                source=ToolSource.BUILTIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "vision"},
            ),
            read_emotions,
        ),
        (
            ToolSpec(
                name="vision_capture_screen",
                title="Capture Screen",
                description="Capture desktop screenshot and perform OCR/UI segmentation",
                permissions=[ToolPermissionLevel.READ],
                source=ToolSource.BUILTIN,
                input_schema={"type": "object", "properties": {}},
                metadata={"subsystem": "vision"},
            ),
            capture_screen,
        ),
        (
            ToolSpec(
                name="vision_find_element",
                title="Find UI Element",
                description="Locate UI element or button on screen by label",
                permissions=[ToolPermissionLevel.READ],
                source=ToolSource.BUILTIN,
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                metadata={"subsystem": "vision"},
            ),
            find_element,
        ),
    ]

    for spec, handler in specs:
        registry.register(spec, handler)
        names.append(spec.name)

    return names
