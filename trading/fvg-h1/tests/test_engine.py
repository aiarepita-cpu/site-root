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


BASE = [
    C(0, 100, 101, 99, 100),
    C(1, 100, 110, 99, 108),   # swing high candidate (110)
    C(2, 108, 109, 95, 96),
    C(3, 96, 115, 95, 112),    # BOS: close 112 > 110 => trend up
    C(4, 112, 113, 108, 109),  # FVG origin candle (SL wick = 108)
    C(5, 109, 130, 108, 129),
    C(6, 129, 135, 118, 133),  # FVG formed candle: zone [113,118]; swing high 135 (body 133)
    C(7, 133, 134, 116, 120),  # touches zone (low 116 in [113,118])
    C(8, 120, 126, 119, 125),  # clears zone (low 119 > 118) -> entry close=125
]


def test_tp_hit():
    candles = BASE + [C(9, 125, 136, 124, 135)]  # high 136 >= TP 133, low 124 > SL 108
    trades, fvgs = run(candles)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_price == 125 and t.sl_price == 108 and t.tp_price == 133
    assert round(t.rr, 4) == round(8 / 17, 4)
    assert t.outcome == "TP" and t.exit_price == 133
    print("test_tp_hit: OK")


def test_sl_hit():
    candles = BASE + [C(9, 125, 126, 107, 108)]  # low 107 <= SL 108
    trades, fvgs = run(candles)
    assert len(trades) == 1
    assert trades[0].outcome == "SL" and trades[0].exit_price == 108
    print("test_sl_hit: OK")


def test_invalidated_by_wick_through_far_edge():
    candles = BASE[:7] + [C(7, 133, 134, 112, 132)]  # low 112 <= far_edge 113
    trades, fvgs = run(candles)
    assert len(trades) == 0
    assert fvgs[0].state == FVGState.INVALIDATED
    print("test_invalidated_by_wick_through_far_edge: OK")


def test_rr_below_threshold_cancels_trade():
    candles = [
        C(0, 100, 101, 99, 100),
        C(1, 100, 110, 99, 108),
        C(2, 108, 109, 95, 96),
        C(3, 96, 115, 95, 112),
        C(4, 112, 113, 108, 109),
        C(5, 109, 125, 108, 124),
        C(6, 126, 130, 118, 128),  # swing-high target only 128 (body) => tiny reward
        C(7, 128, 129, 116, 120),
        C(8, 120, 126, 119, 125),  # entry=125, risk=17, reward=3 => rr=0.176 < 0.3
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 0
    assert fvgs[0].state == FVGState.CANCELLED_RR
    print("test_rr_below_threshold_cancels_trade: OK")


def test_no_fvg_against_trend():
    # Same bearish 3-candle gap pattern as a valid FVG, but trend is up
    # (per BASE prefix) so a bearish FVG must NOT be created.
    candles = BASE[:4] + [
        C(4, 112, 113, 100, 101),  # origin: low=100 (high enough)
        C(5, 101, 102, 90, 91),
        C(6, 91, 92, 85, 86),      # origin.low(100) > formed.high(92) => bearish gap, but trend=up
    ]
    trades, fvgs = run(candles)
    assert len(fvgs) == 0
    print("test_no_fvg_against_trend: OK")


if __name__ == "__main__":
    test_tp_hit()
    test_sl_hit()
    test_invalidated_by_wick_through_far_edge()
    test_rr_below_threshold_cancels_trade()
    test_no_fvg_against_trend()
    print("ALL TESTS PASSED")
