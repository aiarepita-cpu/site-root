"""Hypothesis: 20-day closing-high breakouts on >=1.5x average volume outperform normal-volume breakouts on SPY/QQQ/IWM."""
import math
from typing import Sequence

STRATEGY_NAME = "volume_breakout"
VERSION = 1
HYPOTHESIS = (
    "Breakouts to a 20-day closing high on volume >= 1.5x the prior 20-day average have higher "
    "10-day forward returns than normal-volume breakouts, and the strategy beats buy-and-hold on Sharpe."
)
MEMO = "research/momentum-analyst-2026-10-10.md#idea-3"
UNIVERSE = ("SPY", "QQQ", "IWM")

PARAMS = {
    "breakout_window": 20,
    "volume_window": 20,
    "volume_multiple": 1.5,
    "exit_window": 10,
}

RISK = {
    "target_weight_per_symbol": 1 / 3,
    "stop_loss_pct": None,  # none by design: the 10-day low is the exit
}


# --- Entry -----------------------------------------------------------------
def is_breakout(closes: Sequence[float]) -> bool:
    """Today's close strictly above the highest close of the prior 20 days (today excluded)."""
    n = PARAMS["breakout_window"]
    return len(closes) >= n + 1 and closes[-1] > max(closes[-1 - n:-1])


def is_high_volume(volumes: Sequence[float]) -> bool:
    """Today's volume >= 1.5x the mean of the prior 20 days (today excluded)."""
    n = PARAMS["volume_window"]
    if len(volumes) < n + 1:
        return False
    avg = sum(volumes[-1 - n:-1]) / n
    return volumes[-1] >= PARAMS["volume_multiple"] * avg


def entry_signal(closes: Sequence[float], volumes: Sequence[float], in_position: bool) -> bool:
    if in_position:
        return False
    return is_breakout(closes) and is_high_volume(volumes)


# --- Exit ------------------------------------------------------------------
def exit_signal(closes: Sequence[float], in_position: bool) -> bool:
    """Exit when long and today's close is strictly below the lowest close of the prior 10 days."""
    n = PARAMS["exit_window"]
    if not in_position or len(closes) < n + 1:
        return False
    return closes[-1] < min(closes[-1 - n:-1])


# --- Position sizing -------------------------------------------------------
def position_size(equity: float, price: float, max_position_pct: float) -> int:
    if equity <= 0 or price <= 0:
        return 0
    weight = min(RISK["target_weight_per_symbol"], max_position_pct)
    return math.floor(equity * weight / price)
