"""Unit tests for Plugin SDK & Loader."""

import json
import pytest

from emily.plugins.loader import PluginLoader, PluginState
from emily.plugins.manifest import PluginManifest
from emily.plugins.subsystem import PluginSubsystem


def test_plugin_manifest_validation():
    data = {
        "name": "sample-plugin",
        "version": "1.2.0",
        "description": "Sample plugin test",
        "author": "Emily Devs",
    }
    manifest = PluginManifest.model_validate(data)
    assert manifest.name == "sample-plugin"
    assert manifest.version == "1.2.0"


def test_plugin_loader_discovery(tmp_path):
    p_dir = tmp_path / "plugins" / "my_plugin"
    p_dir.mkdir(parents=True)
    manifest_data = {
        "name": "my_plugin",
        "version": "0.5.0",
        "description": "Dynamic test plugin",
    }
    (p_dir / "emily-plugin.json").write_text(json.dumps(manifest_data), encoding="utf-8")

    loader = PluginLoader(plugins_dir=tmp_path / "plugins")
    plugins = loader.discover_and_load_all()
    assert len(plugins) == 1
    assert plugins[0].manifest.name == "my_plugin"
    assert plugins[0].state == PluginState.LOADED

    loader.enable_plugin("my_plugin")
    assert plugins[0].state == PluginState.ACTIVE


@pytest.mark.asyncio
async def test_plugin_subsystem_lifecycle():
    subsystem = PluginSubsystem()

    class DummyCtx:
        pass

    await subsystem.start(DummyCtx())
    assert subsystem.loader is not None
    await subsystem.stop(DummyCtx())
