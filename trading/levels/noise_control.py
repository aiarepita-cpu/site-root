#!/usr/bin/env python3
"""Control de ruido: corre cada detector sobre caminatas aleatorias.

Por qué el cero es la referencia exacta y no una aproximación: sobre una
caminata sin deriva, una apuesta entre dos barreras a distancia `a` (stop) y
`b` (objetivo) se gana con probabilidad a/(a+b). En unidades de riesgo eso da
expectativa CERO para cualquier R:R. No es una intuición, es el teorema del
muestreo opcional sobre una martingala.

Así que toda desviación del cero sobre ruido mide el sesgo del motor, nunca
una ventaja. Dos usos:

  * detectar bugs. Un sesgo OPTIMISTA (expectativa positiva sobre ruido) es
    dinero imposible. Así se encontraron los dos de la ruta `zone_touch`, que
    daba profit factor 2,02 sobre ruido puro.
  * calibrar. Un sesgo PESIMISTA es el precio de simular con velas: ante una
    vela que toca las dos barreras se acredita el stop. Ese costo crece con
    el R:R, así que no se puede comparar un detector contra el cero teórico:
    hay que compararlo contra SU PROPIO ruido, emparejado por R:R. Eso es lo
    que hace `--comparar`.

Uso:
    python3 noise_control.py                    # tabla de sesgo sobre ruido
    python3 noise_control.py --intrabar tp      # cuánto pesa la convención
    python3 noise_control.py --comparar         # real contra su propio ruido
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
from engine.runner import Config, run

BARRAS = 60_000
SERIES = 5
DATOS = "../fvg-h1/data/XAUUSD_H1_MT5.csv"
CRUZADOS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "SILVER"]
CORTE_HOLDOUT = datetime(2023, 1, 1)

# Bordes de los cubos de R:R. El sesgo del motor crece con el R:R, así que la
# comparación contra ruido se hace dentro de cada cubo y se repondera.
CUBOS = [0.3, 0.75, 1.25, 2.0, 3.0, 5.0, 8.0, 20.0]
MIN_CUBO = 50          # trades de ruido mínimos para usar un cubo


def cubo(rr: float) -> int:
    for k in range(len(CUBOS) - 1):
        if rr < CUBOS[k + 1]:
            return k
    return len(CUBOS) - 2


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
    """Control neutro en modo break_return, sin ninguna lectura del gráfico."""
    if i % 40 or i < 10:
        return []
    c = candles[i]
    L = c.close * 0.01
    if rnd.random() < 0.5:
        price = c.close - rnd.uniform(0.1, 0.5) * L
        return [Level(i, price, BUY, price - 0.4 * L, price + 0.8 * L, "rnd", 48)]
    price = c.close + rnd.uniform(0.1, 0.5) * L
    return [Level(i, price, SELL, price + 0.4 * L, price - 0.8 * L, "rnd", 48)]


def bootstrap_ci(xs, n=3000, seed=17):
    rnd = random.Random(seed)
    b = sorted(sum(rnd.choice(xs) for _ in range(len(xs))) / len(xs) for _ in range(n))
    return b[int(0.025 * n)], b[int(0.975 * n)]


def cosechar(series, ctxs, det, cfg):
    """Devuelve (R, rr) de cada operación cerrada."""
    out = []
    for s, ctx in zip(series, ctxs):
        for t in run(s, det, cfg, ctx=ctx):
            if t.outcome:
                out.append(((t.rr if t.outcome == "TP" else -1.0), t.rr))
    return out


def resumen(obs):
    rs = [r for r, _ in obs]
    gw = sum(r for r in rs if r > 0)
    gl = -sum(r for r in rs if r < 0)
    return {
        "n": len(rs),
        "win": sum(1 for r in rs if r > 0) / len(rs) * 100,
        "rr": sum(rr for _, rr in obs) / len(obs),
        "expR": sum(rs) / len(rs),
        "pf": gw / gl if gl else float("inf"),
    }


# ------------------------------------------------------------------ real
def cargar_reales():
    oro = load_csv(DATOS)
    dev = [c for c in oro if c.timestamp < CORTE_HOLDOUT]
    hold = [c for c in oro if c.timestamp >= CORTE_HOLDOUT]
    for serie in (dev, hold):
        for i, c in enumerate(serie):
            c.index = i
    cruz = []
    for sym in CRUZADOS:
        s = load_csv(f"../fvg-h1/data/cross/{sym}_H1.csv")
        for i, c in enumerate(s):
            c.index = i
        cruz.append(s)
    return {"desarrollo 09-22": [dev], "holdout 23-26": [hold], "cruzado 5 activos": cruz}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("detectores", nargs="*")
    ap.add_argument("--datos", default=DATOS)
    ap.add_argument("--intrabar", default="sl", choices=["sl", "tp"])
    ap.add_argument("--comparar", action="store_true")
    args = ap.parse_args()
    cfg = Config(intrabar=args.intrabar)

    sigma = volatilidad_real(args.datos)
    print(f"volatilidad horaria calibrada sobre datos reales: {sigma*100:.4f}%")
    print(f"{SERIES} caminatas x {BARRAS:,} barras por detector")
    print(f"vela que toca ambas barreras -> se acredita {args.intrabar.upper()}\n")

    series = [caminata(BARRAS, sigma, s) for s in range(1, SERIES + 1)]
    ctxs = [build_ctx(s) for s in series]

    objetivo = dict(DETECTORES)
    objetivo["[control aleatorio]"] = nivel_aleatorio_break
    if args.detectores:
        objetivo = {k: v for k, v in objetivo.items() if k in args.detectores}

    ruido = {}
    print(f"{'detector':>20} {'n':>6} {'win%':>6} {'rr':>6} {'expR':>9} {'pf':>6} "
          f"{'IC95 sobre ruido':>22}  sesgo del motor")
    print("-" * 104)
    for nombre, det in objetivo.items():
        obs = cosechar(series, ctxs, det, cfg)
        if len(obs) < 30:
            print(f"{nombre:>20} {len(obs):>6}   muestra insuficiente")
            continue
        ruido[nombre] = obs
        m, (lo, hi) = resumen(obs), bootstrap_ci([r for r, _ in obs])
        sesgo = (">>> OPTIMISTA <<<" if lo > 0 else
                 "pesimista" if hi < 0 else "neutro")
        print(f"{nombre:>20} {m['n']:>6} {m['win']:>6.1f} {m['rr']:>6.2f} "
              f"{m['expR']:>+9.4f} {m['pf']:>6.3f} "
              f"{f'[{lo:+.4f},{hi:+.4f}]':>22}  {sesgo}")

    print("\nSobre ruido la expectativa teórica es CERO para cualquier R:R.")
    print("OPTIMISTA = dinero imposible: hay un bug. PESIMISTA = costo de")
    print("simular con velas, crece con el R:R; es la línea base a batir.")

    if not args.comparar:
        return

    # ---------------- real contra su propio ruido, emparejado por R:R ------
    print("\n\nREAL CONTRA SU PROPIO RUIDO (emparejado por cubo de R:R)")
    print("Cada operación real se mide contra la expectativa que el mismo")
    print("detector obtuvo sobre ruido con un R:R comparable.\n")
    reales = {k: (v, [build_ctx(s) for s in v]) for k, v in cargar_reales().items()}

    base = {}
    for nombre, obs in ruido.items():
        b = {}
        for k in range(len(CUBOS) - 1):
            rs = [r for r, rr in obs if cubo(rr) == k]
            if len(rs) >= MIN_CUBO:
                b[k] = sum(rs) / len(rs)
        base[nombre] = b

    print(f"{'detector':>20} {'conjunto':>20} {'n':>6} {'expR':>9} {'ruido':>9} "
          f"{'exceso':>9} {'IC95 del exceso':>22}  veredicto")
    print("-" * 122)
    for nombre, det in objetivo.items():
        if nombre not in base or not base[nombre]:
            continue
        for etiqueta, (conj, cs) in reales.items():
            obs = cosechar(conj, cs, det, cfg)
            ex = [r - base[nombre][cubo(rr)] for r, rr in obs
                  if cubo(rr) in base[nombre]]
            if len(ex) < 30:
                print(f"{nombre:>20} {etiqueta:>20} {len(ex):>6}   muestra insuficiente")
                continue
            rs = [r for r, rr in obs if cubo(rr) in base[nombre]]
            lo, hi = bootstrap_ci(ex)
            med = sum(ex) / len(ex)
            v = "VENTAJA" if lo > 0 else "peor que ruido" if hi < 0 else "indistinguible"
            print(f"{nombre:>20} {etiqueta:>20} {len(rs):>6} "
                  f"{sum(rs)/len(rs):>+9.4f} {sum(rs)/len(rs)-med:>+9.4f} "
                  f"{med:>+9.4f} {f'[{lo:+.4f},{hi:+.4f}]':>22}  {v}")

    print("\nSolo cuenta un detector con VENTAJA en los tres conjuntos.")


if __name__ == "__main__":
    main()
