from .models import Candle, Direction, FVG, FVGState, Swing, Trade
from .swings import nearest_swing

MIN_RR = 0.3


def detect_raw_fvg(candles: list[Candle], i: int) -> str | None:
    """Purely geometric 3-candle FVG check on the window ending at i, with
    NO trend filter: returns "up", "down" or None. Trend validation needs
    to know about FVGs (a break only counts if it displaced), and FVG
    tradeability needs to know the trend -- detecting the raw geometry
    first breaks that circularity.
    """
    if i < 2:
        return None
    origin, formed = candles[i - 2], candles[i]
    if origin.high < formed.low:
        return "up"
    if origin.low > formed.high:
        return "down"
    return None


def detect_new_fvg(
    candles: list[Candle],
    i: int,
    trend: str | None,
    leg_origin_low: Swing | None,
    leg_origin_high: Swing | None,
) -> FVG | None:
    """Looks at the 3-candle window ending at i (i-2, i-1, i) and returns a
    new FVG only if it forms in the same direction as `trend`.

    SL = wick of the swing that started the CURRENT structural leg (the
    swing low/high in place at the moment of the BOS/CHoCH that put us
    in this trend -- see TrendTracker.leg_origin_low/high), not just the
    nearest small retracement before this particular FVG. It stays the
    same for every FVG that forms within the same leg. If no such swing
    exists yet (leg started right at the beginning of the data), the
    origin candle's own wick is used as a fallback (an FVG always has
    *something* to risk against, at minimum the candle that created it).
    """
    if i < 2 or trend is None:
        return None
    origin, _mid, formed = candles[i - 2], candles[i - 1], candles[i]

    if trend == "up" and origin.high < formed.low:
        sl_price = leg_origin_low.price if leg_origin_low is not None else origin.low
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
            sl_price=sl_price,   # wick of the swing that started this leg
        )

    if trend == "down" and origin.low > formed.high:
        sl_price = leg_origin_high.price if leg_origin_high is not None else origin.high
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
            sl_price=sl_price,   # wick of the swing that started this leg
        )

    return None


def step_fvg(
    fvg: FVG,
    candle: Candle,
    swings: list[Swing],
    target_n: int = 1,
    h1_index: int | None = None,
    entry_mode: str = "range",
) -> Trade | None:
    """Advances one active FVG (WATCHING or TOUCHED) by one candle.
    Mutates fvg.state in place. Returns a new Trade if this candle
    triggers the entry, else None. Once the state is anything other than
    WATCHING/TOUCHED the FVG is resolved and must not be stepped again.

    `candle` supplies the prices. When driving the zone with a lower
    timeframe, pass the LTF candle here and the current H1 index as
    `h1_index` (used for the swing-target lookup and trade bookkeeping).
    Invalidation and touch are wick-based, so they give identical
    results on either timeframe -- an H1 high/low IS the extreme of its
    sub-candles. Only the entry trigger actually differs.

    `entry_mode` sets how much of the confirming candle must be beyond
    the near edge:
      "range" - the whole candle, wick included (the original H1 rule)
      "body"  - the whole body (open AND close) beyond it
      "close" - the close beyond it, which is what "exceeds it with the
                body" normally means: the body crossed out of the zone,
                as opposed to only a wick poking out.
    """
    if fvg.state not in (FVGState.WATCHING, FVGState.TOUCHED):
        return None
    ref_index = h1_index if h1_index is not None else candle.index
    if ref_index <= fvg.formed_index:
        return None

    bullish = fvg.direction is Direction.BUY
    wick_far = candle.low if bullish else candle.high
    crossed_far = (wick_far <= fvg.far_edge) if bullish else (wick_far >= fvg.far_edge)
    if crossed_far:
        fvg.state = FVGState.INVALIDATED
        return None

    wick_near = candle.low if bullish else candle.high
    inside_zone = (wick_near <= fvg.near_edge) if bullish else (wick_near >= fvg.near_edge)

    if inside_zone:
        fvg.touched = True
        fvg.state = FVGState.TOUCHED

    if entry_mode == "close":
        cleared = (candle.close > fvg.near_edge) if bullish else (candle.close < fvg.near_edge)
    elif entry_mode == "body":
        body = candle.body_bottom if bullish else candle.body_top
        cleared = (body > fvg.near_edge) if bullish else (body < fvg.near_edge)
    else:
        cleared = not inside_zone

    if not cleared or not fvg.touched:
        return None

    return _try_enter(
        fvg, candle, swings,
        want_swing=("high" if bullish else "low"),
        target_n=target_n,
        ref_index=ref_index,
    )


def _try_enter(fvg: FVG, candle: Candle, swings: list[Swing], want_swing: str,
               target_n: int = 1, ref_index: int | None = None) -> Trade | None:
    idx = ref_index if ref_index is not None else candle.index
    entry_price = candle.close
    risk = abs(entry_price - fvg.sl_price)
    if risk <= 0:
        fvg.state = FVGState.CANCELLED_NO_TARGET
        return None

    target = nearest_swing(swings, before_index=idx, want=want_swing, n=target_n)
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
        entry_index=idx,
        entry_price=entry_price,
        sl_price=fvg.sl_price,
        tp_price=tp_price,
        swing_index=target.index,
        risk=risk,
        reward=reward,
        rr=rr,
    )
