"""Strongly typed identifiers for Emily OS entities."""

from __future__ import annotations

import secrets
import time
from typing import NewType

EventId = NewType("EventId", str)
CorrelationId = NewType("CorrelationId", str)
MissionId = NewType("MissionId", str)
AgentId = NewType("AgentId", str)
ToolId = NewType("ToolId", str)
SubsystemId = NewType("SubsystemId", str)
CapabilityId = NewType("CapabilityId", str)


def new_id(prefix: str) -> str:
    """Generate a time-sortable unique id: ``{prefix}_{ms}_{entropy}``."""

    if not prefix or not prefix.replace("_", "").isalnum():
        msg = f"invalid id prefix: {prefix!r}"
        raise ValueError(msg)
    millis = int(time.time() * 1000)
    entropy = secrets.token_hex(6)
    return f"{prefix}_{millis}_{entropy}"


def new_event_id() -> EventId:
    return EventId(new_id("evt"))


def new_correlation_id() -> CorrelationId:
    return CorrelationId(new_id("cor"))


def new_mission_id() -> MissionId:
    return MissionId(new_id("mis"))


def new_agent_id() -> AgentId:
    return AgentId(new_id("agt"))


def new_tool_id() -> ToolId:
    return ToolId(new_id("tol"))


def new_subsystem_id(name: str) -> SubsystemId:
    return SubsystemId(new_id(f"sub_{name}"))
