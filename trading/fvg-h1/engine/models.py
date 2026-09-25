from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    BUY = 1
    SELL = -1


class FVGState(Enum):
    WATCHING = "watching"
    TOUCHED = "touched"
    TRIGGERED = "triggered"
    INVALIDATED = "invalidated"
    CANCELLED_RR = "cancelled_rr"
    CANCELLED_NO_TARGET = "cancelled_no_target"


@dataclass
class Candle:
    index: int
    timestamp: object
    open: float
    high: float
    low: float
    close: float

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)

    @property
    def bullish(self) -> bool:
        return self.close >= self.open


@dataclass
class Swing:
    index: int
    price: float          # wick extreme (high or low)
    body_price: float      # body extreme (close/open) used as TP reference
    direction: str          # "high" or "low"


@dataclass
class FVG:
    id: int
    direction: Direction
    origin_index: int       # candle 1 of the 3-candle pattern ("la vela que inicio el FVG")
    formed_index: int       # candle 3 of the 3-candle pattern (index where the gap is confirmed)
    zone_low: float
    zone_high: float
    far_edge: float          # boundary that, if crossed by a wick, invalidates the FVG
    near_edge: float          # boundary that must be fully cleared (wick incl.) to trigger entry
    sl_price: float           # wick of the origin candle, opposite side of the zone
    state: FVGState = FVGState.WATCHING
    touched: bool = False
    trade_index: int = None   # index of resulting Trade, if any


@dataclass
class Trade:
    id: int
    fvg_id: int
    direction: Direction
    entry_index: int
    entry_price: float
    sl_price: float
    tp_price: float
    swing_index: int
    risk: float
    reward: float
    rr: float
    exit_index: int = None
    exit_price: float = None
    outcome: str = None   # "TP", "SL"
