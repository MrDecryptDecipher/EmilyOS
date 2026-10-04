"""Security Subsystem integration for Emily OS Kernel."""

import logging
from typing import Any

from emily.kernel.subsystem import BaseSubsystem
from emily.security.approvals import ApprovalGateManager
from emily.security.audit import AuditLogger
from emily.security.tokens import CapabilityTokenManager
from emily.security.vault import SecretsVault

logger = logging.getLogger(__name__)


class SecuritySubsystem(BaseSubsystem):
    """Emily Kernel Subsystem for Security, Secrets Vault, Approvals, and Audit Logging."""

    name: str = "security"

    def __init__(self) -> None:
        super().__init__()
        self.vault = SecretsVault()
        self.tokens = CapabilityTokenManager()
        self.approvals = ApprovalGateManager()
        self.audit = AuditLogger()

    async def on_start(self, ctx: Any) -> None:
        logger.info("Starting SecuritySubsystem")
        self.audit.record_event("subsystem_start", "security", {"status": "running"})

    async def on_stop(self, ctx: Any) -> None:
        logger.info("Stopping SecuritySubsystem")
        self.audit.record_event("subsystem_stop", "security", {"status": "stopped"})
