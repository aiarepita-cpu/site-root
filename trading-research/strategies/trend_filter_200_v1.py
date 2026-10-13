"""Hypothesis: SPY/QQQ/IWM held only above their 200-day SMA beat buy-and-hold on Sharpe or cut max drawdown >=25%."""
import math
from typing import Sequence

STRATEGY_NAME = "trend_filter_200"
VERSION = 1
HYPOTHESIS = (
    "Holding each ETF only while its close is above its 200-day SMA improves Sharpe "
    "or cuts max drawdown by at least 25% versus buy-and-hold."
)
MEMO = "research/momentum-analyst-2026-10-10.md#idea-1"
UNIVERSE = ("SPY", "QQQ", "IWM")

PARAMS = {
    "sma_window": 200,
}

# Strategy-level risk. The global caps in config/risk.json are applied on top.
RISK = {
    "target_weight_per_symbol": 1 / 3,  # equal split across the universe
    "stop_loss_pct": None,              # none by design: the SMA cross is the exit
}


def _sma(values: Sequence[float], window: int) -> float:
    return sum(values[-window:]) / window


# --- Entry -----------------------------------------------------------------
def entry_signal(closes: Sequence[float], in_position: bool) -> bool:
    """Enter when flat and today's close is strictly above the 200-day SMA (which includes today)."""
    n = PARAMS["sma_window"]
    if in_position or len(closes) < n:
        return False
    return closes[-1] > _sma(closes, n)


# --- Exit ------------------------------------------------------------------
def exit_signal(closes: Sequence[float], in_position: bool) -> bool:
    """Exit when long and today's close is strictly below the 200-day SMA. Equal to the SMA: hold."""
    n = PARAMS["sma_window"]
    if not in_position or len(closes) < n:
        return False
    return closes[-1] < _sma(closes, n)


# --- Position sizing -------------------------------------------------------
def position_size(equity: float, price: float, max_position_pct: float) -> int:
    """Whole shares for target_weight_per_symbol, capped by the global max_position_pct."""
    if equity <= 0 or price <= 0:
        return 0
    weight = min(RISK["target_weight_per_symbol"], max_position_pct)
    return math.floor(equity * weight / price)
