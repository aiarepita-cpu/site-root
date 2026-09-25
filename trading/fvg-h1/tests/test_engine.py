"""Plain-assert regression tests for the FVG H1 strategy engine.
Run with: python3 tests/test_engine.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.models import Candle, FVGState
from engine.backtest import run


def C(i, o, h, l, c):
    return Candle(index=i, timestamp=i, open=o, high=h, low=l, close=c)


# Shared prefix: seeds a swing high (110), a swing low (100, this is the
# leg-start swing used as SL), a BOS to uptrend (close 112 > 110), and the
# FVG origin/impulse candles. Each test appends its own resolution candles.
BASE6 = [
    C(0, 100, 101, 99, 100),
    C(1, 100, 110, 104, 108),  # swing high candidate (110)
    C(2, 108, 109, 100, 93),   # swing low candidate (100) -> becomes the SL
    C(3, 93, 115, 102, 112),   # BOS: close 112 > 110 => trend up
    C(4, 112, 113, 108, 109),  # FVG origin candle
    C(5, 109, 130, 108, 129),
]


def test_sl_uses_leg_start_swing_not_origin_wick():
    candles = BASE6 + [
        C(6, 129, 135, 118, 134),  # formed candle: zone [113,118]; swing high 135 (body 134)
        C(7, 134, 129, 116, 120), # touches zone (low 116 in [113,118])
        C(8, 120, 126, 119, 125), # clears zone (low 119 > 118) -> entry close=125
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 1
    t = trades[0]
    # SL must be the swing-low wick (100), NOT the origin candle's own
    # wick (108) as in the previous rule.
    assert t.sl_price == 100
    assert t.entry_price == 125 and t.tp_price == 134
    assert round(t.rr, 4) == round(9 / 25, 4)
    print("test_sl_uses_leg_start_swing_not_origin_wick: OK")


def test_tp_hit():
    candles = BASE6 + [
        C(6, 129, 135, 118, 134),
        C(7, 134, 129, 116, 120),
        C(8, 120, 126, 119, 125),
        C(9, 125, 136, 124, 135),  # high 136 >= TP 134, low 124 > SL 100
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 1
    assert trades[0].outcome == "TP" and trades[0].exit_price == 134
    print("test_tp_hit: OK")


def test_sl_hit():
    candles = BASE6 + [
        C(6, 129, 135, 118, 134),
        C(7, 134, 129, 116, 120),
        C(8, 120, 126, 119, 125),
        C(9, 125, 126, 99, 100),  # low 99 <= SL 100
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 1
    assert trades[0].outcome == "SL" and trades[0].exit_price == 100
    print("test_sl_hit: OK")


def test_invalidated_by_wick_through_far_edge():
    candles = BASE6 + [
        C(6, 129, 135, 118, 134),
        C(7, 134, 129, 112, 132),  # low 112 <= far_edge 113
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 0
    assert fvgs[-1].state == FVGState.INVALIDATED
    print("test_invalidated_by_wick_through_far_edge: OK")


def test_rr_below_threshold_cancels_trade():
    candles = BASE6 + [
        C(6, 120, 135, 118, 126),  # small body (126) but still pivot high 135
        C(7, 126, 129, 116, 120),
        C(8, 120, 126, 119, 125),  # entry=125, risk=25 (SL=100), reward=1 => rr=0.04 < 0.3
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 0
    assert fvgs[-1].state == FVGState.CANCELLED_RR
    print("test_rr_below_threshold_cancels_trade: OK")


def test_no_fvg_against_trend():
    # Bearish 3-candle gap pattern, but every close stays above the last
    # confirmed swing low (100) so the trend never flips: it remains up
    # (per BASE6 prefix), so this bearish FVG must NOT be created.
    candles = BASE6[:4] + [
        C(4, 112, 113, 105, 106),  # origin: high=113, low=105
        C(5, 106, 107, 102, 103),
        C(6, 103, 104, 100.5, 101),  # origin.low(105) > formed.high(104) => bearish gap, trend still up
    ]
    trades, fvgs = run(candles)
    assert len(fvgs) == 0
    print("test_no_fvg_against_trend: OK")


def test_no_confirmed_swing_falls_back_to_origin_wick():
    # Trend is confirmed up (BOS at idx3), but no swing LOW has ever been
    # confirmed (price never dipped into a local minimum) by the time the
    # bullish FVG forms at idx6. An FVG always has *something* to risk
    # against -- at minimum the wick of the candle that created it -- so
    # the FVG must still be created, with SL = origin candle's own low.
    candles = [
        C(0, 100, 101, 99, 100),
        C(1, 100, 105, 99, 104),   # swing high candidate (105)
        C(2, 104, 104.5, 99, 104),
        C(3, 104, 112, 103, 111),  # BOS: close 111 > 105 => trend up
        C(4, 111, 113, 108, 110),  # FVG origin: low=108 -> fallback SL
        C(5, 110, 125, 109, 124),
        C(6, 124, 130, 115, 129),  # formed candle: origin.high(113) < formed.low(115)
    ]
    trades, fvgs = run(candles)
    fvg = next(f for f in fvgs if f.origin_index == 4)
    assert fvg.sl_price == 108
    print("test_no_confirmed_swing_falls_back_to_origin_wick: OK")


if __name__ == "__main__":
    test_sl_uses_leg_start_swing_not_origin_wick()
    test_tp_hit()
    test_sl_hit()
    test_invalidated_by_wick_through_far_edge()
    test_rr_below_threshold_cancels_trade()
    test_no_fvg_against_trend()
    test_no_confirmed_swing_falls_back_to_origin_wick()
    print("ALL TESTS PASSED")
