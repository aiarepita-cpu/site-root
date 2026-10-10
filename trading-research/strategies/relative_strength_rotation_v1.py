"""Hypothesis: holding the best positive 6-month performer of SPY/QQQ/IWM monthly beats an equal-weight mix on Sharpe."""
import datetime as dt
import math
from typing import Mapping, Optional, Sequence

STRATEGY_NAME = "relative_strength_rotation"
VERSION = 1
HYPOTHESIS = (
    "At each month-end, holding only the ETF with the highest positive 6-month return "
    "beats a monthly-rebalanced equal-weight SPY/QQQ/IWM portfolio on Sharpe after costs."
)
MEMO = "research/momentum-analyst-2026-10-10.md#idea-2"
UNIVERSE = ("SPY", "QQQ", "IWM")  # order breaks exact ties

PARAMS = {
    "lookback_days": 126,  # ~6 months of trading days
}

RISK = {
    "target_weight": 1.0,   # whole strategy allocation in one ETF, before global caps
    "stop_loss_pct": None,  # none by design: monthly re-ranking is the exit
}


def is_rebalance_day(today: dt.date, next_trading_day: dt.date) -> bool:
    """True on the last trading day of a month."""
    return today.month != next_trading_day.month or today.year != next_trading_day.year


def trailing_return(closes: Sequence[float]) -> Optional[float]:
    n = PARAMS["lookback_days"]
    if len(closes) < n + 1:
        return None
    return closes[-1] / closes[-1 - n] - 1


def select_target(closes_by_symbol: Mapping[str, Sequence[float]]) -> Optional[str]:
    """Symbol with the highest trailing return if it is > 0, else None (cash).
    Any symbol with too little history means no decision (None)."""
    best, best_ret = None, None
    for sym in UNIVERSE:
        r = trailing_return(closes_by_symbol[sym])
        if r is None:
            return None
        if best_ret is None or r > best_ret:
            best, best_ret = sym, r
    return best if best_ret > 0 else None


# --- Entry -----------------------------------------------------------------
def entry_signal(closes_by_symbol, current: Optional[str], rebalance_day: bool) -> Optional[str]:
    """On a rebalance day, return the symbol to buy if the target differs from what is held."""
    if not rebalance_day:
        return None
    target = select_target(closes_by_symbol)
    return target if target is not None and target != current else None


# --- Exit ------------------------------------------------------------------
def exit_signal(closes_by_symbol, current: Optional[str], rebalance_day: bool) -> bool:
    """On a rebalance day, sell the current holding if it is no longer the target (incl. go to cash)."""
    if not rebalance_day or current is None:
        return False
    return select_target(closes_by_symbol) != current


# --- Position sizing -------------------------------------------------------
def position_size(equity: float, price: float, max_position_pct: float) -> int:
    if equity <= 0 or price <= 0:
        return 0
    weight = min(RISK["target_weight"], max_position_pct)
    return math.floor(equity * weight / price)
