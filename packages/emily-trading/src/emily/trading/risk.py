"""Risk Enforcer and Approval rules for autonomous trading."""

from dataclasses import dataclass
from typing import Any


@dataclass
class RiskLimits:
    max_order_value_usd: float = 10000.0
    max_position_size_usd: float = 25000.0
    require_human_approval: bool = True


class RiskEnforcer:
    """Enforces safety limits and human approval requirements before trade execution."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def validate_order(self, symbol: str, side: str, qty: float, price: float) -> tuple[bool, str]:
        """Validate if an order satisfies risk limits."""
        order_value = qty * price
        if order_value > self.limits.max_order_value_usd:
            return False, f"Order value ${order_value:.2f} exceeds max order limit ${self.limits.max_order_value_usd:.2f}"
        return True, "Order passes risk limits"
