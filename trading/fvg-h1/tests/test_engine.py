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


# Shared prefix: seeds a swing high (105) and a BIG swing low (80, this
# is the leg-origin swing used as SL for every FVG in this whole leg),
# then a CHoCH/BOS to uptrend (close 111 > 105), then the FVG origin and
# impulse candles.
BASE6 = [
    C(0, 100, 101, 90, 100),
    C(1, 100, 105, 95, 104),   # swing high candidate (105)
    C(2, 104, 104.5, 80, 93),  # BIG swing low (80) -> leg origin for the whole up-leg
    C(3, 93, 112, 92, 111),    # CHoCH: close 111 > 105 => trend up; leg_origin_low = idx2 (80)
    C(4, 111, 113, 108, 109),  # FVG origin candle (small internal low, NOT used for SL anymore)
    C(5, 109, 130, 108, 129),
]


def test_sl_uses_leg_origin_not_nearest_retracement():
    candles = BASE6 + [
        C(6, 138, 142, 118, 140),  # formed candle: zone [113,118]; swing high 142 (body 140)
        C(7, 140, 141, 116, 138), # touches zone (low 116 in [113,118])
        C(8, 120, 126, 119, 125), # clears zone (low 119 > 118) -> entry close=125
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 1
    t = trades[0]
    # SL must be the leg-origin swing low (80), NOT the small internal
    # low of the origin candle (108) and NOT any nearer retracement low.
    assert t.sl_price == 80
    assert t.entry_price == 125 and t.tp_price == 140
    assert round(t.rr, 4) == round(15 / 45, 4)
    print("test_sl_uses_leg_origin_not_nearest_retracement: OK")


def test_leg_origin_survives_continuation_bos():
    # A second FVG forms further into the SAME uptrend, on the very
    # candle that also breaks a newer swing high (135) -- a continuation
    # BOS, not a reversal. The leg origin must stay at the original 80;
    # it only resets on a trend reversal (CHoCH), never on a
    # continuation break.
    candles = BASE6 + [
        C(6, 129, 135, 118, 133),  # formed: FVG#1, zone [113,118]; swing high 135
        C(7, 133, 134, 116, 120),  # touch#1; swing low 116 confirms here
        C(8, 120, 140, 119, 138),  # clears FVG#1 AND continuation BOS (close 138 > 135)
    ]
    trades, fvgs = run(candles)
    assert fvgs[0].sl_price == 80
    print("test_leg_origin_survives_continuation_bos: OK")


def test_tp_hit():
    candles = BASE6 + [
        C(6, 138, 142, 118, 140),
        C(7, 140, 141, 116, 138),
        C(8, 120, 126, 119, 125),
        C(9, 125, 141, 124, 130),  # high 141 >= TP 140, low 124 > SL 80
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 1
    assert trades[-1].outcome == "TP" and trades[-1].exit_price == 140
    print("test_tp_hit: OK")


def test_sl_hit():
    candles = BASE6 + [
        C(6, 138, 142, 118, 140),
        C(7, 140, 141, 116, 138),
        C(8, 120, 126, 119, 125),
        C(9, 125, 126, 79, 80),  # low 79 <= SL 80
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 1
    assert trades[-1].outcome == "SL" and trades[-1].exit_price == 80
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
    # SL now reaches all the way back to the big leg-origin low (80), so
    # risk is large (45). A nearby, unambitious swing-high target (body
    # only slightly above entry) can't clear the 0.3 R:R floor -- here
    # it doesn't even clear the entry price, so it's rejected outright.
    candles = BASE6 + [
        C(6, 120, 135, 118, 121.5),  # tiny body (121.5) but still pivot high 135
        C(7, 121.5, 129, 116, 120),
        C(8, 120, 126, 119, 125),    # entry=125, target body 121.5 < entry => no valid reward
    ]
    trades, fvgs = run(candles)
    assert len(trades) == 0
    assert fvgs[-1].state == FVGState.CANCELLED_NO_TARGET
    print("test_rr_below_threshold_cancels_trade: OK")


def test_no_fvg_against_trend():
    # Bearish 3-candle gap pattern (origin.low(113) > formed.high(104)),
    # but every close stays above the last confirmed swing low (80) so
    # the trend never flips: it remains up (per BASE6 prefix), so this
    # particular bearish FVG must NOT be created (a benign BUY FVG from
    # an earlier, overlapping 3-candle window may still appear -- that's
    # unrelated and fine).
    from engine.models import Direction

    candles = BASE6[:4] + [
        C(4, 112, 113, 105, 106),  # origin: high=113, low=105
        C(5, 106, 107, 102, 103),
        C(6, 103, 104, 100.5, 101),  # origin.low(105) > formed.high(104) => bearish gap, trend still up
    ]
    trades, fvgs = run(candles)
    assert not any(f.direction is Direction.SELL for f in fvgs)
    print("test_no_fvg_against_trend: OK")


def test_no_confirmed_swing_falls_back_to_origin_wick():
    # Trend is confirmed up (CHoCH at idx3), but no swing LOW has ever
    # been confirmed (price never dipped into a local minimum) by the
    # time the bullish FVG forms at idx6. An FVG always has *something*
    # to risk against -- at minimum the wick of the candle that created
    # it -- so the FVG must still be created, with SL = origin candle's
    # own low.
    candles = [
        C(0, 100, 101, 99, 100),
        C(1, 100, 105, 99, 104),   # swing high candidate (105)
        C(2, 104, 104.5, 99, 104),
        C(3, 104, 112, 103, 111),  # CHoCH: close 111 > 105 => trend up; no swing low exists yet
        C(4, 111, 113, 108, 110),  # FVG origin: low=108 -> fallback SL
        C(5, 110, 125, 109, 124),
        C(6, 124, 130, 115, 129),  # formed candle: origin.high(113) < formed.low(115)
    ]
    trades, fvgs = run(candles)
    fvg = next(f for f in fvgs if f.origin_index == 4)
    assert fvg.sl_price == 108
    print("test_no_confirmed_swing_falls_back_to_origin_wick: OK")


def _trend_series(candles, require_fvg_break):
    from engine.swings import detect_swings
    from engine.trend import TrendTracker
    from engine.fvg_detector import detect_raw_fvg

    tr = TrendTracker(detect_swings(candles, 1), 1,
                      require_fvg_break=require_fvg_break, fvg_window=2)
    out = []
    for c in candles:
        raw = detect_raw_fvg(candles, c.index)
        if raw is not None:
            tr.note_fvg(raw, c.index)
        out.append(tr.update(c))
    return out, tr


def test_break_without_fvg_is_not_a_break():
    # Price grinds above the swing high (110) with no imbalance anywhere:
    # a close beyond it is not a valid break under the FVG rule.
    candles = [
        C(0, 100, 101, 99, 100),
        C(1, 100, 110, 104, 108),  # swing high 110
        C(2, 108, 109, 100, 103),
        C(3, 103, 106, 102, 105),
        C(4, 105, 108, 104, 107),
        C(5, 107, 111, 106, 111),  # close 111 > 110, but no FVG anywhere
        C(6, 111, 112, 108, 111),
    ]
    without, _ = _trend_series(candles, False)
    with_rule, _ = _trend_series(candles, True)
    assert without[-1] == "up"          # old behaviour: counts as a break
    assert all(t is None for t in with_rule)  # new rule: never a break
    print("test_break_without_fvg_is_not_a_break: OK")


def test_break_with_displacement_counts_and_records_its_fvg():
    candles = [
        C(0, 100, 101, 99, 100),
        C(1, 100, 110, 104, 108),  # swing high 110
        C(2, 108, 109, 100, 103),
        C(3, 103, 106, 102, 105),
        C(4, 105, 118, 104, 117),  # displacement candle, close 117 > 110
        C(5, 117, 120, 108, 119),  # FVG completes here: high[3]=106 < low[5]=108
        C(6, 119, 121, 115, 120),
    ]
    with_rule, tr = _trend_series(candles, True)
    # valid, but only confirmed once the FVG completes one candle later
    assert with_rule[4] is None
    assert with_rule[5] == "up"
    assert tr.break_fvg_index == 5
    print("test_break_with_displacement_counts_and_records_its_fvg: OK")


if __name__ == "__main__":
    test_break_without_fvg_is_not_a_break()
    test_break_with_displacement_counts_and_records_its_fvg()
    test_sl_uses_leg_origin_not_nearest_retracement()
    test_leg_origin_survives_continuation_bos()
    test_tp_hit()
    test_sl_hit()
    test_invalidated_by_wick_through_far_edge()
    test_rr_below_threshold_cancels_trade()
    test_no_fvg_against_trend()
    test_no_confirmed_swing_falls_back_to_origin_wick()
    print("ALL TESTS PASSED")
