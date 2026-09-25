from .models import Candle, Direction, FVG, FVGState, Swing, Trade
from .swings import nearest_swing

MIN_RR = 0.3


def detect_new_fvg(candles: list[Candle], i: int, trend: str | None, swings: list[Swing]) -> FVG | None:
    """Looks at the 3-candle window ending at i (i-2, i-1, i) and returns a
    new FVG only if it forms in the same direction as `trend`.

    SL = wick of the swing that started the impulse leg this FVG belongs
    to (the swing low behind a bullish leg, the swing high behind a
    bearish leg) -- not simply the origin candle's wick. If no such
    swing is confirmed yet, there is nothing to risk-manage against and
    the FVG is not created at all.
    """
    if i < 2 or trend is None:
        return None
    origin, _mid, formed = candles[i - 2], candles[i - 1], candles[i]

    if trend == "up" and origin.high < formed.low:
        leg_start = nearest_swing(swings, before_index=formed.index, want="low")
        if leg_start is None:
            return None
        zone_low, zone_high = origin.high, formed.low
        return FVG(
            id=-1,
            direction=Direction.BUY,
            origin_index=origin.index,
            formed_index=formed.index,
            zone_low=zone_low,
            zone_high=zone_high,
            far_edge=zone_low,     # a wick crossing below here invalidates
            near_edge=zone_high,   # must clear above here (wick incl.) to enter
            sl_price=leg_start.price,   # wick of the swing that started this leg
        )

    if trend == "down" and origin.low > formed.high:
        leg_start = nearest_swing(swings, before_index=formed.index, want="high")
        if leg_start is None:
            return None
        zone_low, zone_high = formed.high, origin.low
        return FVG(
            id=-1,
            direction=Direction.SELL,
            origin_index=origin.index,
            formed_index=formed.index,
            zone_low=zone_low,
            zone_high=zone_high,
            far_edge=zone_high,   # a wick crossing above here invalidates
            near_edge=zone_low,    # must clear below here (wick incl.) to enter
            sl_price=leg_start.price,   # wick of the swing that started this leg
        )

    return None


def step_fvg(fvg: FVG, candle: Candle, swings: list[Swing]) -> Trade | None:
    """Advances one active FVG (WATCHING or TOUCHED) by one candle.
    Mutates fvg.state in place. Returns a new Trade if this candle
    triggers the entry, else None. Once the state is anything other than
    WATCHING/TOUCHED the FVG is resolved and must not be stepped again.
    """
    if fvg.state not in (FVGState.WATCHING, FVGState.TOUCHED):
        return None
    if candle.index <= fvg.formed_index:
        return None

    bullish = fvg.direction is Direction.BUY
    wick_far = candle.low if bullish else candle.high
    crossed_far = (wick_far <= fvg.far_edge) if bullish else (wick_far >= fvg.far_edge)
    if crossed_far:
        fvg.state = FVGState.INVALIDATED
        return None

    wick_near = candle.low if bullish else candle.high
    inside_zone = (wick_near <= fvg.near_edge) if bullish else (wick_near >= fvg.near_edge)
    cleared_near = not inside_zone

    if not cleared_near:
        fvg.touched = True
        fvg.state = FVGState.TOUCHED
        return None

    if not fvg.touched:
        # Never actually retraced into the zone yet: nothing to confirm.
        return None

    return _try_enter(fvg, candle, swings, want_swing=("high" if bullish else "low"))


def _try_enter(fvg: FVG, candle: Candle, swings: list[Swing], want_swing: str) -> Trade | None:
    entry_price = candle.close
    risk = abs(entry_price - fvg.sl_price)
    if risk <= 0:
        fvg.state = FVGState.CANCELLED_NO_TARGET
        return None

    target = nearest_swing(swings, before_index=candle.index, want=want_swing)
    if target is None:
        fvg.state = FVGState.CANCELLED_NO_TARGET
        return None

    tp_price = target.body_price
    reward = (tp_price - entry_price) if fvg.direction is Direction.BUY else (entry_price - tp_price)

    if reward <= 0:
        fvg.state = FVGState.CANCELLED_NO_TARGET
        return None

    rr = reward / risk
    if rr < MIN_RR:
        fvg.state = FVGState.CANCELLED_RR
        return None

    fvg.state = FVGState.TRIGGERED
    return Trade(
        id=-1,
        fvg_id=fvg.id,
        direction=fvg.direction,
        entry_index=candle.index,
        entry_price=entry_price,
        sl_price=fvg.sl_price,
        tp_price=tp_price,
        swing_index=target.index,
        risk=risk,
        reward=reward,
        rr=rr,
    )
