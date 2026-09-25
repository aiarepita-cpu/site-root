from .models import Candle, Swing


class TrendTracker:
    """Causal BOS/CHoCH trend tracker.

    - Keeps the most recently CONFIRMED swing high and swing low.
    - A candle's CLOSE breaking above the last swing high => uptrend
      (BOS if already up, CHoCH if it was down/undefined).
    - A candle's CLOSE breaking below the last swing low => downtrend.
    - No lookahead: a swing formed at index k is only usable once
      candle k+1 has closed (see swings.detect_swings).

    A REVERSAL break (CHoCH: trend flips down->up or up->down, or the
    very first break) starts a new "leg", whose origin is the
    opposite-type swing that was the most recent one *at the moment of
    that reversal* -- e.g. the swing low in place right when price first
    broke up out of a downtrend/undefined state. That origin is what
    FVGs use for their SL, and it stays fixed for the *entire* trend,
    through every later continuation BOS (breaking a newer high/low in
    the same direction) and every smaller internal retracement, until
    the next CHoCH starts a genuinely new leg.
    """

    def __init__(self, swings: list[Swing]):
        self._swings_by_confirm_index: dict[int, list[Swing]] = {}
        for s in swings:
            self._swings_by_confirm_index.setdefault(s.index + 1, []).append(s)
        self.last_high: Swing | None = None
        self.last_low: Swing | None = None
        self.trend: str | None = None  # "up" / "down" / None
        self.leg_origin_low: Swing | None = None   # swing low that started the current up-leg
        self.leg_origin_high: Swing | None = None  # swing high that started the current down-leg
        self._broken_high_idx: int | None = None
        self._broken_low_idx: int | None = None

    def update(self, candle: Candle) -> str | None:
        for s in self._swings_by_confirm_index.get(candle.index, []):
            if s.direction == "high":
                self.last_high = s
            else:
                self.last_low = s

        if (
            self.last_high is not None
            and candle.close > self.last_high.price
            and self.last_high.index != self._broken_high_idx
        ):
            is_reversal = self.trend != "up"
            self.trend = "up"
            self._broken_high_idx = self.last_high.index
            if is_reversal:
                self.leg_origin_low = self.last_low
        elif (
            self.last_low is not None
            and candle.close < self.last_low.price
            and self.last_low.index != self._broken_low_idx
        ):
            is_reversal = self.trend != "down"
            self.trend = "down"
            self._broken_low_idx = self.last_low.index
            if is_reversal:
                self.leg_origin_high = self.last_high

        return self.trend
