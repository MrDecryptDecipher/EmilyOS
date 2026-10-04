"""Coding Subsystem integration for Emily OS Kernel."""

import logging
from pathlib import Path
from typing import Any

from emily.coding.git_service import GitService
from emily.coding.indexer import RepositoryIndexer
from emily.coding.reviewer import CodeReviewEngine
from emily.kernel.subsystem import BaseSubsystem

logger = logging.getLogger(__name__)


class CodingSubsystem(BaseSubsystem):
    """Emily Kernel Subsystem for Coding Workbench, Indexing, and Code Review."""

    name: str = "coding"

    def __init__(self, root_dir: Path | str | None = None) -> None:
        super().__init__()
        self.root_dir = Path(root_dir) if root_dir else Path(".")
        self.indexer = RepositoryIndexer(self.root_dir)
        self.git_service = GitService(self.root_dir)
        self.git = self.git_service
        self.reviewer = CodeReviewEngine()

    async def on_start(self, ctx: Any) -> None:
        logger.info("Starting CodingSubsystem")

    async def on_stop(self, ctx: Any) -> None:
        logger.info("Stopping CodingSubsystem")
