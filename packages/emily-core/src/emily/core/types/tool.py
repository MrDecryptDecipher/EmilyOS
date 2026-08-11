"""Tool permission levels."""

from enum import StrEnum


class ToolPermissionLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    DESKTOP = "desktop"
    BROWSER = "browser"
    PRIVILEGED = "privileged"
