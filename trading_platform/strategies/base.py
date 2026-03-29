from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol

import pandas as pd


@dataclass
class Signal:
    timestamp: pd.Timestamp
    symbol: str
    side: str
    confidence: float
    reason: str
    take_profit_pct: float
    stop_loss_pct: float


class Strategy(Protocol):
    name: str

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> list[Signal]:
        ...

    def parameters(self) -> Dict[str, float]:
        ...
