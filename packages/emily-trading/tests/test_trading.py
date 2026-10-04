"""Unit tests for Trading & Risk Subsystem."""

import pytest
from emily.trading.broker import PaperTradingBroker
from emily.trading.risk import RiskEnforcer, RiskLimits
from emily.trading.subsystem import TradingSubsystem


def test_paper_trading_buy_sell():
    broker = PaperTradingBroker(initial_cash=50000.0)
    order = broker.place_order(symbol="AAPL", side="buy", qty=10, price=150.0)
    assert order.status == "filled"
    assert broker.cash == 48500.0

    summary = broker.get_portfolio_summary()
    assert summary["cash"] == 48500.0
    assert summary["positions_value"] == 1500.0
    assert summary["total_portfolio_value"] == 50000.0
    assert len(summary["positions"]) == 1

    sell_order = broker.place_order(symbol="AAPL", side="sell", qty=10, price=160.0)
    assert sell_order.status == "filled"
    assert broker.cash == 50100.0
    assert len(broker.get_portfolio_summary()["positions"]) == 0


def test_risk_enforcer_limits():
    risk = RiskEnforcer(limits=RiskLimits(max_order_value_usd=5000.0))
    ok, msg = risk.validate_order("GOOGL", "buy", 10, 100.0)
    assert ok is True

    ok2, msg2 = risk.validate_order("GOOGL", "buy", 100, 100.0)
    assert ok2 is False
    assert "exceeds max order limit" in msg2


@pytest.mark.asyncio
async def test_trading_subsystem_lifecycle():
    subsystem = TradingSubsystem()

    class DummyCtx:
        pass

    await subsystem.start(DummyCtx())
    assert subsystem.broker is not None
    await subsystem.stop(DummyCtx())
