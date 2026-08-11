"""Emily OS core package — shared types, errors, and ports."""

from emily.core.errors import EmilyError, ErrorCode
from emily.core.ids import AgentId, CorrelationId, EventId, MissionId, ToolId, new_id
from emily.core.version import __version__

__all__ = [
    "AgentId",
    "CorrelationId",
    "EmilyError",
    "ErrorCode",
    "EventId",
    "MissionId",
    "ToolId",
    "__version__",
    "new_id",
]
