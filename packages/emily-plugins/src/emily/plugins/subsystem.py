"""Plugin Subsystem integration for Emily OS Kernel."""

import logging
from typing import Any

from emily.kernel.subsystem import BaseSubsystem
from emily.plugins.loader import PluginLoader

logger = logging.getLogger(__name__)


class PluginSubsystem(BaseSubsystem):
    """Emily Kernel Subsystem for Plugin discovery, loading, and hot reloading."""

    name: str = "plugins"

    def __init__(self, plugins_dir: Any = None) -> None:
        super().__init__()
        self.loader = PluginLoader(plugins_dir=plugins_dir) if plugins_dir else PluginLoader()

    async def on_start(self, ctx: Any) -> None:
        logger.info("Starting PluginSubsystem")
        self.loader.discover_and_load_all()

    async def on_stop(self, ctx: Any) -> None:
        logger.info("Stopping PluginSubsystem")
