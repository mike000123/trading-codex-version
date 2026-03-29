from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from trading_platform.config import Mode
from trading_platform.risk.controls import RiskDecision
from trading_platform.strategies.base import Signal


@dataclass
class OrderResult:
    accepted: bool
    mode: str
    order_id: str
    details: dict[str, Any]


class OrderRouter:
    def __init__(self, mode: Mode, live_armed: bool = False) -> None:
        self.mode = mode
        self.live_armed = live_armed

    def _paper_order(self, signal: Signal, qty: float, risk: RiskDecision) -> OrderResult:
        return OrderResult(
            accepted=True,
            mode=Mode.PAPER.value,
            order_id=f"paper-{signal.symbol}-{signal.timestamp.isoformat()}",
            details={
                "symbol": signal.symbol,
                "qty": qty,
                "side": signal.side,
                "reason": signal.reason,
                "allocation_usd": risk.allocation_usd,
                "take_profit_pct": signal.take_profit_pct,
                "stop_loss_pct": signal.stop_loss_pct,
            },
        )

    def _live_order(self, signal: Signal, qty: float, risk: RiskDecision) -> OrderResult:
        if not self.live_armed:
            return OrderResult(False, Mode.LIVE.value, "", {"error": "Live mode not armed in UI confirmation."})

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        paper_env = os.getenv("ALPACA_PAPER", "true").lower() == "true"

        if not api_key or not secret_key:
            return OrderResult(False, Mode.LIVE.value, "", {"error": "Missing Alpaca credentials in env vars."})

        client = TradingClient(api_key=api_key, secret_key=secret_key, paper=paper_env)
        order = MarketOrderRequest(
            symbol=signal.symbol,
            qty=max(1, int(qty)),
            side=OrderSide.BUY if signal.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        submitted = client.submit_order(order_data=order)
        return OrderResult(
            accepted=True,
            mode=Mode.LIVE.value,
            order_id=str(submitted.id),
            details={
                "symbol": signal.symbol,
                "qty": qty,
                "side": signal.side,
                "allocation_usd": risk.allocation_usd,
                "alpaca_status": str(submitted.status),
            },
        )

    def route(self, signal: Signal, latest_price: float, risk: RiskDecision) -> OrderResult:
        if not risk.approved:
            return OrderResult(False, self.mode.value, "", {"error": risk.reason})

        qty = risk.allocation_usd / max(1e-9, latest_price)
        if self.mode == Mode.PAPER:
            return self._paper_order(signal, qty=qty, risk=risk)
        return self._live_order(signal, qty=qty, risk=risk)
