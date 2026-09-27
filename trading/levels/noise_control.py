#!/usr/bin/env python3
"""Control de ruido: corre cada detector sobre caminatas aleatorias.

Sobre una serie sin estructura ninguna estrategia puede tener ventaja, así
que la expectativa tiene que dar cero. Si un detector gana sobre ruido, el
edge es un bug del motor o del propio detector, no del mercado.

Así se descubrieron los dos sesgos de la ruta `zone_touch` (ver
RESULTADOS.md): daba profit factor 2,02 sobre ruido puro.

Uso:
    python3 noise_control.py                 # todos los detectores
    python3 noise_control.py martillo fib_golden
"""
import argparse
import math
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from engine.candles import Candle, load_csv
from engine.levels import BUY, SELL, DETECTORES, Level, build_ctx
from engine.runner import run

BARRAS = 60_000
SERIES = 5


def volatilidad_real(path: str) -> float:
    cs = load_csv(path)
    rets = [math.log(cs[i].close / cs[i - 1].close) for i in range(1, len(cs))]
    return (sum(r * r for r in rets) / len(rets)) ** 0.5


def caminata(n: int, sigma: float, seed: int) -> list[Candle]:
    """Caminata aleatoria sin memoria, con OHLC construido de 4 subpasos."""
    rnd = random.Random(seed)
    px, out = 2000.0, []
    t0 = datetime(2010, 1, 4)          # arranca lunes
    for i in range(n):
        o = px
        pasos = [o * math.exp(rnd.gauss(0, sigma / 2)) for _ in range(4)]
        c = pasos[-1]
        out.append(Candle(i, t0 + timedelta(hours=i), o,
                          max([o, c] + pasos), min([o, c] + pasos), c))
        px = c
    return out


def nivel_aleatorio_break(candles, i, ctx, rnd=random.Random(1234)):
    """Control neutro en modo break_return, para comparar contra los 6."""
    if i % 40 or i < 10:
        return []
    c = candles[i]
    L = c.close * 0.01
    if rnd.random() < 0.5:
        price = c.close - rnd.uniform(0.1, 0.5) * L
        return [Level(i, price, BUY, price - 0.4 * L, price + 0.8 * L, "rnd", 48)]
    price = c.close + rnd.uniform(0.1, 0.5) * L
    return [Level(i, price, SELL, price + 0.4 * L, price - 0.8 * L, "rnd", 48)]


def bootstrap_ci(rs: list[float], n: int = 3000, seed: int = 17) -> tuple[float, float]:
    rnd = random.Random(seed)
    b = sorted(sum(rnd.choice(rs) for _ in range(len(rs))) / len(rs) for _ in range(n))
    return b[int(0.025 * n)], b[int(0.975 * n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("detectores", nargs="*")
    ap.add_argument("--datos", default="../fvg-h1/data/XAUUSD_H1_MT5.csv")
    args = ap.parse_args()

    sigma = volatilidad_real(args.datos)
    print(f"volatilidad horaria calibrada sobre datos reales: {sigma*100:.4f}%")
    print(f"{SERIES} caminatas x {BARRAS:,} barras por detector\n")

    series = [caminata(BARRAS, sigma, s) for s in range(1, SERIES + 1)]
    ctxs = [build_ctx(s) for s in series]

    objetivo = dict(DETECTORES)
    objetivo["[control aleatorio]"] = nivel_aleatorio_break
    if args.detectores:
        objetivo = {k: v for k, v in objetivo.items() if k in args.detectores}

    print(f"{'detector':>20} {'n':>6} {'win%':>6} {'rr':>6} {'expR':>9} {'pf':>6} "
          f"{'IC95 sobre ruido':>22}  veredicto")
    print("-" * 100)
    for nombre, det in objetivo.items():
        rs, rrs = [], []
        for s, ctx in zip(series, ctxs):
            for t in run(s, det, ctx=ctx):
                if t.outcome:
                    rs.append(t.rr if t.outcome == "TP" else -1.0)
                    rrs.append(t.rr)
        if len(rs) < 30:
            print(f"{nombre:>20} {len(rs):>6}   muestra insuficiente")
            continue
        lo, hi = bootstrap_ci(rs)
        gw = sum(r for r in rs if r > 0)
        gl = -sum(r for r in rs if r < 0)
        win = sum(1 for r in rs if r > 0) / len(rs) * 100
        # sobre ruido la expectativa debe contener el cero
        veredicto = "OK" if lo <= 0 <= hi else ">>> SESGO <<<"
        print(f"{nombre:>20} {len(rs):>6} {win:>6.1f} {sum(rrs)/len(rrs):>6.2f} "
              f"{sum(rs)/len(rs):>+9.4f} {gw/gl:>6.3f} "
              f"{f'[{lo:+.4f},{hi:+.4f}]':>22}  {veredicto}")

    print("\nLectura: sobre ruido la expectativa debe contener el cero.")
    print("Un intervalo que lo excluye señala un sesgo en el motor o el detector,")
    print("no una ventaja de mercado.")


if __name__ == "__main__":
    main()
