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
from engine.levels import (BUY, SELL, DETECTORES, Level, build_ctx,
                           fib_golden_zone)
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


SUBPASOS = 12


def caminata(n: int, sigma: float, seed: int) -> list[Candle]:
    """Caminata aleatoria, con la barra construida de subpasos ACUMULADOS.

    El detalle importa mas que todo el resto del archivo. Una primera version
    sorteaba los 4 subpasos cada uno desde la APERTURA en vez de desde el
    subpaso anterior. Eso no es una caminata: dentro de la barra el precio
    revierte a la apertura, asi que las mechas se inflan y se retraen. Con
    mechas espurias la barrera mas cercana se toca de mas, y como el stop esta
    a 1R, un detector con objetivo lejano perdia sistematicamente. Daba hasta
    -0,27R sobre ruido puro y parecia un sesgo pesimista del motor.

    Con subpasos acumulados el camino es una martingala de verdad y la
    expectativa de cualquier par de barreras vuelve a ser cero.
    """
    rnd = random.Random(seed)
    paso = sigma / SUBPASOS ** 0.5
    px, out = 2000.0, []
    t0 = datetime(2010, 1, 4)          # arranca lunes
    for i in range(n):
        o = px
        hi = lo = o
        for _ in range(SUBPASOS):
            px *= math.exp(rnd.gauss(0, paso))
            hi, lo = max(hi, px), min(lo, px)
        out.append(Candle(i, t0 + timedelta(hours=i), o, hi, lo, px))
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


def fib_al_cierre(candles, i, ctx):
    """fib_golden con entrada al cierre de la vela del toque.

    La regla conservadora de `zone_touch` (en la vela del toque solo puede
    acreditarse el stop) cuesta -0,29R sobre ruido, asi que mezcla el
    resultado del detector con el lastre del motor. Entrando al cierre la
    vela del toque queda en el pasado y el lastre desaparece.
    """
    out = []
    for lv in fib_golden_zone(candles, i, ctx):
        lv.entry_mode = "zone_touch_close"
        out.append(lv)
    return out


def barrido_rr(sigma: float, series_n: int) -> None:
    """Mide el sesgo del motor en funcion del R:P, con geometria fija.

    El detector de este barrido no lee el grafico: coloca la entrada en el
    cierre de una barra cada 40, riesgo fijo del 0,4% del precio y objetivo a
    un multiplo dado. Sobre una martingala se gana con probabilidad
    1/(1+rr) exactamente, asi que el exceso de acierto mide el sesgo del
    motor sin ninguna decision de estrategia de por medio.

    Es la pieza que decide si un "detector optimista" lo es de verdad: si el
    exceso crece con el R:P, el sesgo es mecanico y lo comparten todos los
    detectores, y la referencia correcta no es el cero sino el control
    emparejado por R:P.
    """
    series = [caminata(BARRAS, sigma, k) for k in range(1, series_n + 1)]
    ctxs = [build_ctx(s) for s in series]
    print(f"{'rr':>5} {'n':>6} {'acierto':>8} {'1/(1+rr)':>9} {'exceso':>8} "
          f"{'sigmas':>7} {'expR':>9} {'IC95 de expR':>21} {'dur':>6}")
    print("-" * 92)
    for objetivo in (1.0, 2.0, 3.0, 5.0, 8.0):
        rnd = random.Random(7)

        def det(candles, i, ctx, _o=objetivo, _r=rnd):
            if i % 40 or i < 10:
                return []
            c = candles[i]
            L = c.close * 0.004
            if _r.random() < 0.5:
                return [Level(i, c.close, BUY, c.close - L, c.close + _o * L, "x", 96)]
            return [Level(i, c.close, SELL, c.close + L, c.close - _o * L, "x", 96)]

        cer = [t for s, ctx in zip(series, ctxs)
               for t in run(s, det, Config(max_rr=25.0), ctx=ctx) if t.outcome]
        rs = [(t.rr if t.outcome == "TP" else -1.0) for t in cer]
        p = sum(1 for r in rs if r > 0) / len(rs)
        esp = sum(1.0 / (1.0 + t.rr) for t in cer) / len(cer)
        se = (p * (1 - p) / len(cer)) ** 0.5
        lo, hi = bootstrap_ci(rs)
        dur = sum(t.exit_index - t.entry_index for t in cer) / len(cer)
        print(f"{objetivo:>5.1f} {len(cer):>6} {100*p:>7.2f}% {100*esp:>8.2f}% "
              f"{100*(p-esp):>+7.2f} {(p-esp)/se:>7.2f} {sum(rs)/len(rs):>+9.4f} "
              f"{f'[{lo:+.4f},{hi:+.4f}]':>21} {dur:>6.1f}")
    print("\nsigmas = a cuantos errores estandar esta el acierto de 1/(1+rr).")
    print("Si el exceso crece con el R:P, el sesgo es mecanico y lo comparten")
    print("todos los detectores: la referencia es el control emparejado, no el cero.")


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
def cargar_reales(path: str = DATOS, corte: datetime = CORTE_HOLDOUT,
                  cruzados: bool = True):
    oro = load_csv(path)
    dev = [c for c in oro if c.timestamp < corte]
    hold = [c for c in oro if c.timestamp >= corte]
    for serie in (dev, hold):
        for i, c in enumerate(serie):
            c.index = i
    cruz = []
    for sym in (CRUZADOS if cruzados else []):
        s = load_csv(f"../fvg-h1/data/cross/{sym}_H1.csv")
        for i, c in enumerate(s):
            c.index = i
        cruz.append(s)
    sets = {f"desarrollo <{corte.date()}": [dev], f"holdout >={corte.date()}": [hold]}
    if cruz:
        sets["cruzado 5 activos"] = cruz
    return sets


def main() -> None:
    global SUBPASOS
    ap = argparse.ArgumentParser()
    ap.add_argument("detectores", nargs="*")
    ap.add_argument("--datos", default=DATOS,
                    help="serie para calibrar la volatilidad del ruido")
    ap.add_argument("--reales", default=None,
                    help="serie a medir en --comparar (por defecto, el oro H1)")
    ap.add_argument("--corte", default=None,
                    help="fecha AAAA-MM-DD que separa desarrollo de holdout")
    ap.add_argument("--intrabar", default="sl", choices=["sl", "tp"])
    ap.add_argument("--comparar", action="store_true")
    ap.add_argument("--barrido-rr", action="store_true",
                    help="mide el sesgo del motor en funcion del R:P")
    ap.add_argument("--subpasos", type=int, default=None,
                    help="resolucion intrabarra de la caminata")
    ap.add_argument("--series", type=int, default=SERIES,
                    help="caminatas por detector; subirlo estrecha el IC")
    ap.add_argument("--fib-al-cierre", action="store_true",
                    help="mide fib_golden entrando al cierre de la vela del toque")
    args = ap.parse_args()
    cfg = Config(intrabar=args.intrabar)
    if args.subpasos:
        SUBPASOS = args.subpasos

    sigma = volatilidad_real(args.datos)
    print(f"volatilidad horaria calibrada sobre datos reales: {sigma*100:.4f}%")
    print(f"{args.series} caminatas x {BARRAS:,} barras por detector")
    print(f"{SUBPASOS} subpasos por vela")
    print(f"vela que toca ambas barreras -> se acredita {args.intrabar.upper()}\n")

    if args.barrido_rr:
        barrido_rr(sigma, args.series)
        return

    series = [caminata(BARRAS, sigma, s) for s in range(1, args.series + 1)]
    ctxs = [build_ctx(s) for s in series]

    objetivo = dict(DETECTORES)
    objetivo["[control aleatorio]"] = nivel_aleatorio_break
    if args.fib_al_cierre:
        objetivo["fib_golden"] = fib_al_cierre
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
    corte = (datetime.strptime(args.corte, "%Y-%m-%d") if args.corte
             else CORTE_HOLDOUT)
    crudos = cargar_reales(args.reales or DATOS, corte,
                           cruzados=args.reales is None)
    reales = {k: (v, [build_ctx(s) for s in v]) for k, v in crudos.items()}

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
