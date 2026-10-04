"""Emily OS — Plugin SDK & Lifecycle Loader."""

from emily.plugins.loader import PluginLoader, PluginState
from emily.plugins.manifest import PluginManifest
from emily.plugins.subsystem import PluginSubsystem

__all__ = [
    "PluginLoader",
    "PluginManifest",
    "PluginState",
    "PluginSubsystem",
]
