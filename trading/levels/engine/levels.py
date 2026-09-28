"""Detectores de nivel.

Los 9 reels del canal comparten una sola mecanica (romper un nivel con
cuerpo, esperar el regreso, entrar en la confirmacion) y se diferencian
solo en de donde sale el nivel. Cada detector de este modulo produce esos
niveles; el motor en `runner.py` aplica la mecanica comun.

Todo lo caro (pivotes fractales, limites de sesion) se precomputa una vez
en `Ctx` y los detectores lo consultan en O(1): recalcularlo por barra
convertia el backtest en O(n^2) y no terminaba sobre 78.000 velas.
"""
from dataclasses import dataclass, field
from datetime import datetime

from .candles import Candle

BUY, SELL = 1, -1


@dataclass
class Level:
    """Un nivel operable.

    `index` es la barra en la que el nivel pasa a ser conocido: el motor
    nunca lo mira antes, para no usar informacion del futuro.
    `sl_price` va del lado opuesto a la direccion de la ruptura.
    """
    index: int
    price: float
    direction: int
    sl_price: float
    tp_price: float | None
    tag: str
    expires_after: int = 96
    # objetivo como multiplo del riesgo, para los reels que fijan "al doble"
    # en vez de apuntar a un extremo previo. Se usa solo si tp_price es None.
    tp_r_multiple: float | None = None
    # "break_return": romper con cuerpo, esperar el regreso y confirmar
    #                 (la mecanica de los 9 reels de asimetricos)
    # "zone_touch":   entrar al tocar el nivel, sin ruptura previa
    #                 (la estrategia Fibonacci: orden limite en la golden zone)
    # "zone_touch_close": igual, pero entrando al cierre de la vela del toque,
    #                 para que no quede ninguna ambiguedad intrabarra
    entry_mode: str = "break_return"


@dataclass
class Ctx:
    """Estructuras precomputadas, compartidas por todos los detectores."""
    n: int
    pivot_highs: list[tuple[int, float]]
    pivot_lows: list[tuple[int, float]]
    # cuantos pivotes estan CONFIRMADOS al cerrar la barra i (indice + n <= i)
    highs_avail: list[int]
    lows_avail: list[int]
    # para cada barra: indice de inicio del dia actual y del dia anterior
    day_start: list[int]
    prev_day_start: list[int]
    extremes: dict[int, tuple[float, float]] = field(default_factory=dict)

    def avail_highs(self, i: int) -> list[tuple[int, float]]:
        return self.pivot_highs[: self.highs_avail[i]]

    def avail_lows(self, i: int) -> list[tuple[int, float]]:
        return self.pivot_lows[: self.lows_avail[i]]

    def day_extremes(self, start: int, end: int) -> tuple[float, float]:
        """Maximo y minimo entre [start, end), memorizado."""
        key = start * 1_000_003 + end
        hit = self.extremes.get(key)
        if hit is None:
            hit = (max(c.high for c in self._candles[start:end]),
                   min(c.low for c in self._candles[start:end]))
            self.extremes[key] = hit
        return hit


def build_ctx(candles: list[Candle], n: int = 2) -> Ctx:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    total = len(candles)
    for k in range(n, total - n):
        b = candles[k]
        if all(b.high > candles[k - j].high and b.high > candles[k + j].high
               for j in range(1, n + 1)):
            highs.append((k, b.high))
        if all(b.low < candles[k - j].low and b.low < candles[k + j].low
               for j in range(1, n + 1)):
            lows.append((k, b.low))

    highs_avail, lows_avail = [0] * total, [0] * total
    hp = lp = 0
    for i in range(total):
        while hp < len(highs) and highs[hp][0] + n <= i:
            hp += 1
        while lp < len(lows) and lows[lp][0] + n <= i:
            lp += 1
        highs_avail[i], lows_avail[i] = hp, lp

    day_start, prev_day_start = [0] * total, [-1] * total
    cur_start, prev_start = 0, -1
    for i in range(1, total):
        if candles[i].timestamp.date() != candles[i - 1].timestamp.date():
            prev_start, cur_start = cur_start, i
        day_start[i], prev_day_start[i] = cur_start, prev_start

    ctx = Ctx(n, highs, lows, highs_avail, lows_avail, day_start, prev_day_start)
    ctx._candles = candles
    return ctx


def _body_top(c: Candle) -> float:
    return max(c.open, c.close)


def _body_bottom(c: Candle) -> float:
    return min(c.open, c.close)


# ---------------------------------------------------------------- #7
def yesterday_close(candles: list[Candle], i: int, ctx: Ctx) -> list[Level]:
    """Reel Ddm3-ufsQa0 — cierre de la vela diaria de ayer.

    El sesgo lo da el signo de la vela de ayer: si cerro alcista solo se
    buscan compras. Nace en la primera barra del dia nuevo, cuando el
    cierre de ayer ya es un dato cerrado.
    """
    if i == 0 or ctx.day_start[i] != i or ctx.prev_day_start[i] < 0:
        return []
    y_start, y_end = ctx.prev_day_start[i], i
    y_open, y_close = candles[y_start].open, candles[y_end - 1].close
    y_high, y_low = ctx.day_extremes(y_start, y_end)

    if y_close > y_open:
        return [Level(i, y_close, BUY, y_low, y_high, "ayer_cierre", 24)]
    if y_close < y_open:
        return [Level(i, y_close, SELL, y_high, y_low, "ayer_cierre", 24)]
    return []


# ---------------------------------------------------------------- #3
def trendline(candles: list[Candle], i: int, ctx: Ctx, pivots: int = 3) -> list[Level]:
    """Reel DdtTge6sVIf — recta que une tres maximos (o tres minimos).

    Solo se emite cuando acaba de confirmarse un pivote nuevo: reemitirla
    en cada barra llenaba el motor de niveles duplicados.
    """
    out: list[Level] = []
    for avail, prev_avail, direction, tag in (
        (ctx.avail_highs(i), ctx.highs_avail[i - 1] if i else 0, BUY, "lt_bajista"),
        (ctx.avail_lows(i), ctx.lows_avail[i - 1] if i else 0, SELL, "lt_alcista"),
    ):
        if len(avail) == prev_avail or len(avail) < pivots:
            continue                       # sin pivote nuevo, no se reemite
        pts = avail[-pivots:]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        nx = len(xs)
        mx, my = sum(xs) / nx, sum(ys) / nx
        den = sum((x - mx) ** 2 for x in xs)
        if den == 0:
            continue
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
        if (direction == BUY and slope >= 0) or (direction == SELL and slope <= 0):
            continue                       # la recta debe oponerse a la ruptura
        price = my + slope * (i - mx)
        if direction == BUY:
            out.append(Level(i, price, BUY, min(p[1] for p in pts[-2:]), pts[0][1], tag, 24))
        else:
            out.append(Level(i, price, SELL, max(p[1] for p in pts[-2:]), pts[0][1], tag, 24))
    return out


# ---------------------------------------------------------------- #6
def hammer_sweep(candles: list[Candle], i: int, ctx: Ctx, lookback: int = 20,
                 wick_ratio: float = 2.0) -> list[Level]:
    """Reel DdoJLD4sGam — martillo que barre un extremo previo.

    La mecha tiene que ser al menos `wick_ratio` veces el cuerpo y perforar
    el extremo de las ultimas `lookback` barras. El nivel es el 50% de esa
    mecha, que es donde el reel deja la orden limite.
    """
    if i < lookback + 1:
        return []
    c = candles[i]
    body = abs(c.close - c.open)
    if body <= 0:
        return []
    lo = i - lookback
    prior_low = min(p.low for p in candles[lo:i])
    prior_high = max(p.high for p in candles[lo:i])

    if _body_bottom(c) - c.low >= wick_ratio * body and c.low < prior_low:
        return [Level(i, (c.low + _body_bottom(c)) / 2, BUY, c.low, prior_high, "martillo", 12)]
    if c.high - _body_top(c) >= wick_ratio * body and c.high > prior_high:
        return [Level(i, (c.high + _body_top(c)) / 2, SELL, c.high, prior_low, "martillo", 12)]
    return []


# ---------------------------------------------------------------- #9
def shoulder_sweep(candles: list[Candle], i: int, ctx: Ctx) -> list[Level]:
    """Reel DdkNwK8s7YS — hombro-cabeza-hombro leido como barrido.

    La "cabeza" es la vela que barre el extremo del hombro izquierdo y
    cierra el cuerpo de vuelta del otro lado. El nivel es ese extremo.
    """
    highs, lows = ctx.avail_highs(i), ctx.avail_lows(i)
    c = candles[i]
    out: list[Level] = []
    if highs:
        sh_idx, sh_price = highs[-1]
        if sh_idx < i and c.high > sh_price and _body_top(c) < sh_price:
            neck = min((p for k, p in lows if k > sh_idx), default=None)
            if neck is not None:
                out.append(Level(i, sh_price, SELL, c.high, neck, "hombro", 24))
    if lows:
        sl_idx, sl_price = lows[-1]
        if sl_idx < i and c.low < sl_price and _body_bottom(c) > sl_price:
            neck = max((p for k, p in highs if k > sl_idx), default=None)
            if neck is not None:
                out.append(Level(i, sl_price, BUY, c.low, neck, "hombro", 24))
    return out


# ---------------------------------------------------------------- #5
def daily_sweep(candles: list[Candle], i: int, ctx: Ctx) -> list[Level]:
    """Reel DdqyZYfMDyh — barrido del extremo de la vela diaria anterior.

    Si el dia en curso barre el minimo de ayer se buscan compras con
    objetivo en el maximo de ayer, y al reves.
    """
    d0, dp = ctx.day_start[i], ctx.prev_day_start[i]
    if dp < 0 or i == d0:
        return []
    y_high, y_low = ctx.day_extremes(dp, d0)
    cur = candles[i]
    today_high, today_low = ctx.day_extremes(d0, i)

    if cur.low < y_low <= today_low:
        return [Level(i, y_low, BUY, cur.low, y_high, "barrido_diario", 24)]
    if cur.high > y_high >= today_high:
        return [Level(i, y_high, SELL, cur.high, y_low, "barrido_diario", 24)]
    return []


# ---------------------------------------------------------------- #2 / #8
def session_range(candles: list[Candle], i: int, ctx: Ctx, open_hour: int = 13) -> list[Level]:
    """Reels DdwFG7rsoRm y Ddlt9w8Mxba — rango de la primera vela de sesion.

    APROXIMACION: los reels usan la vela de 15M de las 9:30 de Nueva York
    y con datos horarios lo mas cercano es la vela de las 13:00 UTC. No es
    fiel al original y su resultado debe leerse con esa salvedad.
    """
    cur = candles[i]
    if cur.timestamp.hour != open_hour:
        return []
    # el reel fija el objetivo "al doble" del riesgo, no en un extremo previo
    return [
        Level(i, cur.high, BUY, cur.low, None, "rango_sesion", 8, tp_r_multiple=2.0),
        Level(i, cur.low, SELL, cur.high, None, "rango_sesion", 8, tp_r_multiple=2.0),
    ]


DETECTORES = {
    "ayer_cierre": yesterday_close,
    "trendline": trendline,
    "martillo": hammer_sweep,
    "hombro": shoulder_sweep,
    "barrido_diario": daily_sweep,
    "rango_sesion": session_range,
}


# ---------------------------------------------------------------- Fibonacci
def fib_golden_zone(candles: list[Candle], i: int, ctx: Ctx,
                    lo_ratio: float = 0.5, hi_ratio: float = 0.618,
                    sl_ratio: float = 0.786, tp_ratio: float = 1.272) -> list[Level]:
    """Reel DdyNFhCohRO — retroceso a la golden zone tras un CHoCH.

    Tras un cambio de caracter se traza Fibonacci sobre el tramo que lo
    produjo y se compra al retroceder a la zona 0.5-0.618, con el stop
    debajo del 0.786 y el objetivo en la extension 1.272.

    El nivel publicado es el borde superior de la zona (el 0.5): el motor
    entra al tocarlo, que es el equivalente a dejar la orden limite ahi.
    """
    highs, lows = ctx.avail_highs(i), ctx.avail_lows(i)
    if not highs or not lows:
        return []
    c = candles[i]
    out: list[Level] = []

    # --- CHoCH alcista: el cierre supera el ultimo swing high ---
    h_idx, h_price = highs[-1]
    prior_lows = [(k, p) for k, p in lows if k < h_idx]
    if prior_lows and c.close > h_price and candles[i - 1].close <= h_price:
        x_idx, x_price = prior_lows[-1]
        leg = h_price - x_price
        if leg > 0:
            out.append(Level(
                i, h_price - lo_ratio * leg, BUY,
                h_price - sl_ratio * leg,
                x_price + tp_ratio * leg,
                "fib_golden", 48, entry_mode="zone_touch"))

    # --- CHoCH bajista: el cierre perfora el ultimo swing low ---
    l_idx, l_price = lows[-1]
    prior_highs = [(k, p) for k, p in highs if k < l_idx]
    if prior_highs and c.close < l_price and candles[i - 1].close >= l_price:
        x_idx, x_price = prior_highs[-1]
        leg = x_price - l_price
        if leg > 0:
            out.append(Level(
                i, l_price + lo_ratio * leg, SELL,
                l_price + sl_ratio * leg,
                x_price - tp_ratio * leg,
                "fib_golden", 48, entry_mode="zone_touch"))
    return out


DETECTORES["fib_golden"] = fib_golden_zone


# ------------------------------------------------- escalera del CHoCH (reel Dd0y-0HhK55)
def choch_ladder(candles: list[Candle], i: int, ctx: Ctx,
                 entrada: float = 5.0, stop: float = 5.5, objetivo: float = 3.0,
                 exigir_ind: bool = True, sentido: str = "contra",
                 entry_mode: str = "zone_touch_close") -> list[Level]:
    """Reel Dd0y-0HhK55 — "USE this Fibo for Sniper Entry". No es Fibonacci.

    Los precios de las lineas etiquetadas se midieron en los dos ejemplos del
    video y dan la MISMA escalera: anclada en el tramo del CHoCH, con los
    niveles en multiplos exactos de MEDIO tramo. Ejemplo 1 (tramo 6,820) y
    ejemplo 2 (tramo 8,268) coinciden al tercer decimal en -3,5 -3 -1,5 -1
    0 +1 +2 +3 +3,5 +5 +5,5. Un Fibonacci tiene los niveles desigualmente
    espaciados (0,236 / 0,382 / 0,5 / 0,618 / 0,786); esto es una rejilla
    uniforme, asi que el nombre del video es incorrecto.

    Las zonas grises del video son las bandas de medio tramo en +-3/3,5 y
    +5/5,5, y las cajas de posicion arrancan en el borde de una zona con el
    stop del otro lado. Con entrada en +5, stop en +5,5 y objetivo en +3 el
    R:P sale 4,0, que es el valor que muestran dos de las cajas (4,06 y 3,38).

    Estructura exigida, leida de las etiquetas BOS / choch / IND:
      1. un swing low L, luego un swing high H que BARRE el high anterior
         (eso es el inducement: `exigir_ind`)
      2. el precio cierra de vuelta por debajo de L -> CHoCH bajista
      3. tramo = H - L, y la escalera se proyecta hacia abajo desde H

    `sentido="contra"` opera a favor del retroceso (comprar abajo tras un
    CHoCH bajista), que es lo que muestran las cajas del video.
    `sentido="favor"` sigue la rotura, para medir si la polaridad importa.
    """
    highs, lows = ctx.avail_highs(i), ctx.avail_lows(i)
    if not highs or not lows:
        return []
    c, prev = candles[i], candles[i - 1]
    out: list[Level] = []

    def _emitir(ancla: float, leg: float, signo: int, tag: str) -> None:
        """signo=-1 proyecta hacia abajo (CHoCH bajista), +1 hacia arriba."""
        nivel = ancla + signo * entrada * leg
        sl = ancla + signo * stop * leg
        tp = ancla + signo * objetivo * leg
        if sentido == "contra":
            d = BUY if signo < 0 else SELL
        else:
            d = SELL if signo < 0 else BUY
            nivel, tp = ancla + signo * 1.0 * leg, ancla + signo * entrada * leg
            sl = ancla
        out.append(Level(i, nivel, d, sl, tp, tag, 96, entry_mode=entry_mode))

    # --- CHoCH bajista: cierre por debajo del ultimo swing low ---
    l_idx, l_price = lows[-1]
    posteriores = [(k, p) for k, p in highs if k > l_idx]
    anteriores = [(k, p) for k, p in highs if k < l_idx]
    if posteriores and c.close < l_price and prev.close >= l_price:
        h_idx, h_price = posteriores[-1]
        barrio = bool(anteriores) and h_price > anteriores[-1][1]
        if (barrio or not exigir_ind) and h_price > l_price:
            _emitir(h_price, h_price - l_price, -1, "escalera")

    # --- CHoCH alcista: cierre por encima del ultimo swing high ---
    h_idx, h_price = highs[-1]
    posteriores = [(k, p) for k, p in lows if k > h_idx]
    anteriores = [(k, p) for k, p in lows if k < h_idx]
    if posteriores and c.close > h_price and prev.close <= h_price:
        l_idx, l_price = posteriores[-1]
        barrio = bool(anteriores) and l_price < anteriores[-1][1]
        if (barrio or not exigir_ind) and h_price > l_price:
            _emitir(l_price, h_price - l_price, +1, "escalera")
    return out


DETECTORES["escalera"] = choch_ladder
