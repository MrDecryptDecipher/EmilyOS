"""Isolated dynamic plugin loader and hot reload manager."""

import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Any

from emily.plugins.manifest import PluginManifest

logger = logging.getLogger(__name__)


class PluginState(StrEnum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class LoadedPlugin:
    def __init__(self, manifest: PluginManifest, plugin_dir: Path) -> None:
        self.manifest = manifest
        self.plugin_dir = plugin_dir
        self.state: PluginState = PluginState.LOADED

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.manifest.name,
            "version": self.manifest.version,
            "description": self.manifest.description,
            "state": self.state.value,
            "path": str(self.plugin_dir),
        }


class PluginLoader:
    """Discovers, validates, and manages hot reloadable plugins."""

    def __init__(self, plugins_dir: Path | str | None = None) -> None:
        self.plugins_dir = Path(plugins_dir) if plugins_dir else Path("plugins")
        self._plugins: dict[str, LoadedPlugin] = {}

    def discover_and_load_all(self) -> list[LoadedPlugin]:
        """Scan plugins directory for valid emily-plugin.json manifests."""
        if not self.plugins_dir.exists():
            return []

        for p_dir in self.plugins_dir.iterdir():
            if p_dir.is_dir():
                manifest_file = p_dir / "emily-plugin.json"
                if manifest_file.exists():
                    try:
                        data = json.loads(manifest_file.read_text(encoding="utf-8"))
                        manifest = PluginManifest.model_validate(data)
                        plugin = LoadedPlugin(manifest, p_dir)
                        self._plugins[manifest.name] = plugin
                        logger.info("Loaded plugin %s v%s", manifest.name, manifest.version)
                    except Exception as e:
                        logger.error("Failed to load plugin from %s: %s", p_dir, e)

        return list(self._plugins.values())

    def enable_plugin(self, name: str) -> bool:
        """Enable an active plugin."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.state = PluginState.ACTIVE
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin.state = PluginState.DISABLED
            return True
        return False

    def list_plugins() -> list[LoadedPlugin]:
        return list(self._plugins.values())
