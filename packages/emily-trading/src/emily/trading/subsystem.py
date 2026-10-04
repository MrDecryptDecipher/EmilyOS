"""Trading Subsystem integration for Emily OS Kernel."""

import logging
from typing import Any

from emily.kernel.subsystem import BaseSubsystem
from emily.trading.broker import PaperTradingBroker
from emily.trading.risk import RiskEnforcer

logger = logging.getLogger(__name__)


class TradingSubsystem(BaseSubsystem):
    """Emily Kernel Subsystem for Paper Trading, Risk Limits, and Portfolio Management."""

    name: str = "trading"

    def __init__(self) -> None:
        super().__init__()
        self.broker = PaperTradingBroker()
        self.risk = RiskEnforcer()

    async def on_start(self, ctx: Any) -> None:
        logger.info("Starting TradingSubsystem")

    async def on_stop(self, ctx: Any) -> None:
        logger.info("Stopping TradingSubsystem")
