from .models import Candle, Swing


class TrendTracker:
    """Causal BOS/CHoCH trend tracker.

    - Keeps the most recently CONFIRMED swing high and swing low.
    - A candle's CLOSE breaking above the last swing high => uptrend
      (BOS if already up, CHoCH if it was down/undefined).
    - A candle's CLOSE breaking below the last swing low => downtrend.
    - No lookahead: a swing formed at index k is only usable once
      candle k+n has closed (see swings.detect_swings).

    A REVERSAL break (CHoCH: trend flips down->up or up->down, or the
    very first break) starts a new "leg", whose origin is the
    opposite-type swing that was the most recent one *at the moment of
    that reversal*. That origin is what FVGs use for their SL, and it
    stays fixed for the entire trend, through every later continuation
    BOS and every internal retracement, until the next CHoCH.

    With `require_fvg_break`, a break only counts if the move that made
    it displaced -- i.e. left an FVG in the same direction within
    `fvg_window` candles before the breaking candle, or on the candle
    right after it. A high taken out by a slow drift with no imbalance
    is not a break at all. Because an FVG completing one candle after
    the break still counts, breaks are resolved with a one-candle
    deferral.
    """

    def __init__(
        self,
        swings: list[Swing],
        n: int = 1,
        require_fvg_break: bool = False,
        fvg_window: int = 2,
    ):
        self._swings_by_confirm_index: dict[int, list[Swing]] = {}
        for s in swings:
            self._swings_by_confirm_index.setdefault(s.index + n, []).append(s)
        self.require_fvg_break = require_fvg_break
        self.fvg_window = fvg_window

        self.last_high: Swing | None = None
        self.last_low: Swing | None = None
        self.trend: str | None = None  # "up" / "down" / None
        self.leg_origin_low: Swing | None = None
        self.leg_origin_high: Swing | None = None
        # index of the FVG that validated the break starting the current leg
        self.break_fvg_index: int | None = None

        self._broken_high_idx: int | None = None
        self._broken_low_idx: int | None = None
        self._fvg_up_indices: list[int] = []
        self._fvg_down_indices: list[int] = []
        self._pending: dict | None = None

    def note_fvg(self, direction: str, formed_index: int) -> None:
        """Register a raw (geometry-only) FVG so breaks can be validated."""
        if direction == "up":
            self._fvg_up_indices.append(formed_index)
        else:
            self._fvg_down_indices.append(formed_index)

    def _fvg_validating(self, direction: str, break_index: int) -> int | None:
        pool = self._fvg_up_indices if direction == "up" else self._fvg_down_indices
        lo = break_index - self.fvg_window
        hi = break_index + 1
        best = None
        for idx in reversed(pool):
            if idx < lo:
                break
            if lo <= idx <= hi:
                best = idx if best is None else max(best, idx)
        return best

    def _apply(self, direction: str, broken_swing: Swing, leg_candidate: Swing | None,
               fvg_index: int | None) -> None:
        is_reversal = self.trend != direction
        self.trend = direction
        if direction == "up":
            self._broken_high_idx = broken_swing.index
        else:
            self._broken_low_idx = broken_swing.index
        if is_reversal:
            if direction == "up":
                self.leg_origin_low = leg_candidate
            else:
                self.leg_origin_high = leg_candidate
            self.break_fvg_index = fvg_index

    def update(self, candle: Candle) -> str | None:
        for s in self._swings_by_confirm_index.get(candle.index, []):
            if s.direction == "high":
                self.last_high = s
            else:
                self.last_low = s

        # resolve a break that was waiting to see whether it displaced
        if self._pending is not None and candle.index > self._pending["break_index"]:
            p = self._pending
            fvg_idx = self._fvg_validating(p["dir"], p["break_index"])
            if fvg_idx is not None:
                self._apply(p["dir"], p["swing"], p["leg_candidate"], fvg_idx)
            self._pending = None

        broke_high = (
            self.last_high is not None
            and candle.close > self.last_high.price
            and self.last_high.index != self._broken_high_idx
        )
        broke_low = (
            self.last_low is not None
            and candle.close < self.last_low.price
            and self.last_low.index != self._broken_low_idx
        )

        if broke_high or broke_low:
            direction = "up" if broke_high else "down"
            swing = self.last_high if broke_high else self.last_low
            leg_candidate = self.last_low if broke_high else self.last_high

            if not self.require_fvg_break:
                self._apply(direction, swing, leg_candidate, None)
            else:
                fvg_idx = self._fvg_validating(direction, candle.index)
                if fvg_idx is not None:
                    self._apply(direction, swing, leg_candidate, fvg_idx)
                else:
                    # an FVG may still complete on the next candle
                    self._pending = {
                        "dir": direction,
                        "swing": swing,
                        "leg_candidate": leg_candidate,
                        "break_index": candle.index,
                    }

        return self.trend
