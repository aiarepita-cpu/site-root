"""Motor comun a los 9 reels.

Mecanica unica, identica en todos ellos:

  1. un detector publica un nivel
  2. el precio lo ROMPE con CUERPO (el cierre queda del otro lado;
     "la mecha no cuenta" es literal en 5 de los 9 reels)
  3. el precio REGRESA al nivel (no se entra en la ruptura:
     "ahi compran casi todos")
  4. una vela CONFIRMA cerrando de nuevo con cuerpo del lado de la ruptura
  5. SL del otro lado del nivel, TP en el extremo previo

Lo unico que cambia entre reels es el paso 1.
"""
from dataclasses import dataclass, field

from .candles import Candle
from .levels import BUY, SELL, Ctx, Level, build_ctx


@dataclass
class Trade:
    tag: str
    direction: int
    entry_index: int
    entry_price: float
    sl_price: float
    tp_price: float
    risk: float
    reward: float
    rr: float
    exit_index: int | None = None
    outcome: str | None = None


@dataclass
class _Active:
    level: Level
    broken_at: int | None = None
    returned: bool = False


@dataclass
class Config:
    min_rr: float = 0.3
    max_rr: float = 20.0          # descarta objetivos absurdos
    cost_per_trade_r: float = 0.0  # costo en R, aplicado al resultado
    allow_directions: tuple = (BUY, SELL)


def run(candles: list[Candle], detector, cfg: Config = Config(),
        detector_kwargs: dict | None = None, ctx: Ctx | None = None) -> list[Trade]:
    kw = detector_kwargs or {}
    if ctx is None:
        ctx = build_ctx(candles)
    active: list[_Active] = []
    trades: list[Trade] = []
    open_trade: Trade | None = None

    for i, bar in enumerate(candles):
        # --- 1) resolver la operacion abierta -------------------------
        if open_trade is not None and i > open_trade.entry_index:
            d = open_trade.direction
            hit_sl = bar.low <= open_trade.sl_price if d == BUY else bar.high >= open_trade.sl_price
            hit_tp = bar.high >= open_trade.tp_price if d == BUY else bar.low <= open_trade.tp_price
            if hit_sl:                       # peor caso ante ambiguedad intrabarra
                open_trade.outcome, open_trade.exit_index = "SL", i
                open_trade = None
            elif hit_tp:
                open_trade.outcome, open_trade.exit_index = "TP", i
                open_trade = None

        # --- 2) avanzar los niveles vivos -----------------------------
        still: list[_Active] = []
        for a in active:
            lv = a.level
            if i <= lv.index or i - lv.index > lv.expires_after:
                continue
            d = lv.direction

            # --- entrada por toque de zona (Fibonacci): sin ruptura previa ---
            if lv.entry_mode == "zone_touch":
                touched = bar.low <= lv.price if d == BUY else bar.high >= lv.price
                if not touched:
                    still.append(a)
                    continue
                if open_trade is not None or d not in cfg.allow_directions:
                    still.append(a)
                    continue
                t = _open_trade(lv, bar, i, cfg, entry_price=lv.price)
                if t is not None:
                    trades.append(t)
                    # La vela de entrada se resuelve AQUI, y de forma simetrica.
                    # Descartar solo las que tocan el stop (y quedarse con las
                    # que tocan el objetivo) elimina los perdedores inmediatos
                    # y conserva los ganadores inmediatos: sobre ruido puro eso
                    # solo ya llevaba el acierto del 27% teorico al 42%.
                    # En la vela de entrada solo se puede acreditar el STOP.
                    # El extremo favorable de esa vela (su maximo en una compra)
                    # suele ser ANTERIOR al toque que nos hizo entrar, asi que
                    # cobrarlo como objetivo seria una ganancia imposible: eso
                    # solo llevaba el acierto sobre ruido del 27% teorico al 31%.
                    hit_sl = bar.low <= t.sl_price if d == BUY else bar.high >= t.sl_price
                    if hit_sl:
                        t.outcome, t.exit_index = "SL", i
                    else:
                        open_trade = t
                continue

            if a.broken_at is None:
                # ruptura con CUERPO
                broke = bar.close > lv.price if d == BUY else bar.close < lv.price
                if broke:
                    a.broken_at = i
                still.append(a)
                continue

            # ya roto: el precio tiene que volver a tocar el nivel
            if not a.returned:
                touched = bar.low <= lv.price if d == BUY else bar.high >= lv.price
                if touched:
                    a.returned = True
                # si el cierre se va del lado del SL, el nivel murio
                failed = bar.close < lv.sl_price if d == BUY else bar.close > lv.sl_price
                if not failed:
                    still.append(a)
                continue

            # regreso hecho: confirmacion con cuerpo del lado de la ruptura
            confirmed = bar.close > lv.price if d == BUY else bar.close < lv.price
            if not confirmed:
                failed = bar.close < lv.sl_price if d == BUY else bar.close > lv.sl_price
                if not failed:
                    still.append(a)
                continue

            if open_trade is not None or d not in cfg.allow_directions:
                still.append(a)
                continue

            t = _open_trade(lv, bar, i, cfg)
            if t is not None:
                trades.append(t)
                open_trade = t
            # el nivel se consume igual, haya entrado o no
        active = still

        # --- 3) publicar niveles nuevos -------------------------------
        for lv in detector(candles, i, ctx, **kw):
            active.append(_Active(lv))

    return trades


def _open_trade(lv: Level, bar: Candle, i: int, cfg: Config,
                entry_price: float | None = None) -> Trade | None:
    entry = bar.close if entry_price is None else entry_price
    risk = abs(entry - lv.sl_price)
    if risk <= 0:
        return None

    if lv.tp_price is not None:
        tp = lv.tp_price
    elif lv.tp_r_multiple is not None:
        tp = entry + lv.direction * lv.tp_r_multiple * risk
    else:
        return None

    reward = (tp - entry) if lv.direction == BUY else (entry - tp)
    if reward <= 0:
        return None
    rr = reward / risk
    if rr < cfg.min_rr or rr > cfg.max_rr:
        return None
    return Trade(lv.tag, lv.direction, i, entry, lv.sl_price, tp, risk, reward, rr)


def summarize(trades: list[Trade], cost_r: float = 0.0) -> dict:
    closed = [t for t in trades if t.outcome]
    if not closed:
        return {"n": 0}
    rs = [((t.rr if t.outcome == "TP" else -1.0) - cost_r) for t in closed]
    wins = sum(1 for t in closed if t.outcome == "TP")
    gw = sum(r for r in rs if r > 0)
    gl = -sum(r for r in rs if r < 0)
    eq, peak, dd = 0.0, 0.0, 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    n = len(rs)
    mean = sum(rs) / n
    var = sum((r - mean) ** 2 for r in rs) / (n - 1) if n > 1 else 0.0
    sd = var ** 0.5
    return {
        "n": n,
        "win_pct": round(100 * wins / n, 1),
        "rr_medio": round(sum(t.rr for t in closed) / n, 3),
        "exp_R": round(mean, 4),
        "net_R": round(sum(rs), 2),
        "pf": round(gw / gl, 3) if gl > 0 else None,
        "maxdd_R": round(dd, 2),
        "t_stat": round(mean / (sd / n ** 0.5), 2) if sd > 0 and n > 1 else None,
    }
