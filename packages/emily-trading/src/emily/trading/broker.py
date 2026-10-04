"""Abstract broker interface and Paper Trading broker implementation."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from emily.core.ids import new_id


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_entry_price) * self.quantity


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str  # buy, sell
    qty: float
    price: float
    status: str = "filled"  # pending, filled, rejected
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class PaperTradingBroker:
    """Simulated Paper Trading broker for safe testing."""

    def __init__(self, initial_cash: float = 100000.0) -> None:
        self.cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._orders: list[Order] = []

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch current real quote for symbol from live market."""
        import urllib.request
        import json
        
        symbol = symbol.upper()
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode())
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                return {"symbol": symbol, "price": float(price)}
        except Exception:
            # Secondary query2 fallback
            try:
                url2 = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
                req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                with urllib.request.urlopen(req2, timeout=6) as response2:
                    data2 = json.loads(response2.read().decode())
                    price = data2['chart']['result'][0]['meta']['regularMarketPrice']
                    return {"symbol": symbol, "price": float(price)}
            except Exception as e2:
                raise ValueError(f"Could not fetch live market quote for '{symbol}': {e2}") from e2

    def get_portfolio(self) -> dict[str, Any]:
        """Return portfolio summary."""
        return self.get_portfolio_summary()

    def place_order(self, symbol: str, side: str, qty: float, price: float) -> Order:
        """Place a buy or sell paper trade order."""
        total_cost = qty * price
        symbol = symbol.upper()

        if side.lower() == "buy":
            if self.cash < total_cost:
                raise ValueError(f"Insufficient funds for order. Required: ${total_cost:.2f}, Available: ${self.cash:.2f}")
            self.cash -= total_cost
            if symbol in self._positions:
                pos = self._positions[symbol]
                new_qty = pos.quantity + qty
                new_avg = ((pos.quantity * pos.avg_entry_price) + total_cost) / new_qty
                self._positions[symbol] = Position(symbol, new_qty, new_avg, price)
            else:
                self._positions[symbol] = Position(symbol, qty, price, price)

        elif side.lower() == "sell":
            if symbol not in self._positions or self._positions[symbol].quantity < qty:
                raise ValueError(f"Insufficient shares to sell. Symbol: {symbol}, Requested: {qty}")
            pos = self._positions[symbol]
            self.cash += total_cost
            new_qty = pos.quantity - qty
            if new_qty == 0:
                del self._positions[symbol]
            else:
                self._positions[symbol] = Position(symbol, new_qty, pos.avg_entry_price, price)

        order = Order(
            order_id=new_id("order"),
            symbol=symbol,
            side=side.lower(),
            qty=qty,
            price=price,
            status="filled",
        )
        self._orders.append(order)
        return order

    def get_portfolio_summary(self) -> dict[str, Any]:
        """Return total portfolio value, cash balance, and active positions."""
        position_val = sum(p.market_value for p in self._positions.values())
        return {
            "cash": round(self.cash, 2),
            "positions_value": round(position_val, 2),
            "total_portfolio_value": round(self.cash + position_val, 2),
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "avg_entry_price": p.avg_entry_price,
                    "current_price": p.current_price,
                    "pnl": round(p.unrealized_pnl, 2),
                }
                for p in self._positions.values()
            ],
        }
