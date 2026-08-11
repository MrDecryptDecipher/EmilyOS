"""Memory kind taxonomy."""

from enum import StrEnum


class MemoryKind(StrEnum):
    WORKING = "working"
    TASK = "task"
    CONVERSATION = "conversation"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    EPISODIC = "episodic"
    VECTOR = "vector"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    EXECUTION_HISTORY = "execution_history"
    FAILURE_HISTORY = "failure_history"
    REFLECTION_HISTORY = "reflection_history"
    MISSION_HISTORY = "mission_history"
    PREFERENCES = "preferences"
    ENVIRONMENT_STATE = "environment_state"
    WORLD_MODEL = "world_model"
