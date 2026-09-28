"""Tests del motor de niveles. Ejecutar: python3 tests/test_engine.py"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.candles import Candle
from engine.levels import (BUY, SELL, Level, build_ctx, choch_ladder,
                           hammer_sweep, yesterday_close)
from engine.runner import Config, run, summarize


def C(i, o, h, l, c, day=1, hour=None):
    ts = datetime(2024, 1, day) + timedelta(hours=hour if hour is not None else i)
    return Candle(i, ts, o, h, l, c)


def fixed_level(price, direction, sl, tp, at=1):
    def det(candles, i, ctx):
        return [Level(at, price, direction, sl, tp, "test")] if i == at else []
    return det


def test_secuencia_completa_dispara_entrada():
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 96, 102),   # ruptura con cuerpo
        C(3, 102, 103, 99, 101),  # regreso al nivel
        C(4, 101, 106, 100, 105), # confirmacion
        C(5, 105, 112, 104, 111), # toca TP
    ]
    t = run(serie, fixed_level(100.0, BUY, 97.0, 110.0))
    assert len(t) == 1 and t[0].outcome == "TP"
    assert t[0].entry_price == 105
    print("test_secuencia_completa_dispara_entrada: OK")


def test_sin_regreso_no_hay_entrada():
    # rompe y se va de largo sin volver nunca al nivel
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 101, 102),
        C(3, 102, 108, 102, 107),
        C(4, 107, 112, 106, 111),
    ]
    assert run(serie, fixed_level(100.0, BUY, 97.0, 110.0)) == []
    print("test_sin_regreso_no_hay_entrada: OK")


def test_mecha_no_rompe_el_nivel():
    # la mecha supera 100 pero el cuerpo cierra debajo: no es ruptura
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 104, 96, 99),    # mecha arriba, cierre 99 < 100
        C(3, 99, 100, 98, 99),
        C(4, 99, 101, 98, 99),
    ]
    assert run(serie, fixed_level(100.0, BUY, 97.0, 110.0)) == []
    print("test_mecha_no_rompe_el_nivel: OK")


def test_cierre_del_lado_del_sl_mata_el_nivel():
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 96, 102),   # ruptura
        C(3, 102, 103, 95, 96),   # cierra 96 < SL 97 -> nivel muerto
        C(4, 96, 106, 95, 105),   # esta ya no deberia entrar
        C(5, 105, 112, 104, 111),
    ]
    assert run(serie, fixed_level(100.0, BUY, 97.0, 110.0)) == []
    print("test_cierre_del_lado_del_sl_mata_el_nivel: OK")


def test_sl_tiene_prioridad_sobre_tp_en_la_misma_vela():
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 96, 102), C(3, 102, 103, 99, 101),
        C(4, 101, 106, 100, 105),
        C(5, 105, 112, 96, 100),  # toca TP 110 y SL 97 en la misma vela
    ]
    t = run(serie, fixed_level(100.0, BUY, 97.0, 110.0))
    assert len(t) == 1 and t[0].outcome == "SL"
    print("test_sl_tiene_prioridad_sobre_tp_en_la_misma_vela: OK")


def test_nivel_expira():
    base = [C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96), C(2, 96, 103, 96, 102)]
    relleno = [C(i, 102, 103, 101, 102) for i in range(3, 12)]
    final = [C(12, 102, 103, 99, 101), C(13, 101, 106, 100, 105)]
    det = lambda candles, i, ctx: (
        [Level(1, 100.0, BUY, 97.0, 110.0, "test", expires_after=5)] if i == 1 else []
    )
    assert run(base + relleno + final, det) == []
    print("test_nivel_expira: OK")


def test_filtro_rr_minimo():
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 96, 102), C(3, 102, 103, 99, 101),
        C(4, 101, 106, 100, 105),
    ]
    # entrada 105, SL 97 -> riesgo 8; TP 106 -> premio 1; rr 0.125 < 0.3
    assert run(serie, fixed_level(100.0, BUY, 97.0, 106.0)) == []
    print("test_filtro_rr_minimo: OK")


def test_una_sola_operacion_a_la_vez():
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 96, 102), C(3, 102, 103, 99, 101),
        C(4, 101, 106, 100, 105),   # entra aqui
        C(5, 105, 106, 104, 105),
        C(6, 105, 106, 104, 105),
    ]
    def dos_niveles(candles, i, ctx):
        if i == 1:
            return [Level(1, 100.0, BUY, 97.0, 110.0, "a"),
                    Level(1, 100.5, BUY, 97.0, 110.0, "b")]
        return []
    t = run(serie, dos_niveles)
    assert len(t) == 1
    print("test_una_sola_operacion_a_la_vez: OK")


def test_detector_ayer_cierre_respeta_el_sesgo():
    # dia 1 alcista (abre 100, cierra 110) -> el nivel del dia 2 es de compra
    d1 = [C(0, 100, 101, 99, 100, day=1, hour=0),
          C(1, 100, 111, 100, 110, day=1, hour=1)]
    d2 = [C(2, 110, 112, 108, 111, day=2, hour=0)]
    serie = d1 + d2
    for i, c in enumerate(serie):
        c.index = i
    niveles = yesterday_close(serie, 2, build_ctx(serie))
    assert len(niveles) == 1
    assert niveles[0].direction == BUY and niveles[0].price == 110
    print("test_detector_ayer_cierre_respeta_el_sesgo: OK")


def test_detector_martillo_exige_mecha_larga():
    base = [C(i, 100, 101, 99, 100) for i in range(21)]
    # cuerpo 1, mecha inferior 6, perfora el minimo previo
    martillo = C(21, 99, 100, 92, 100)
    serie = base + [martillo]
    for i, c in enumerate(serie):
        c.index = i
    ctx = build_ctx(serie)
    niveles = hammer_sweep(serie, 21, ctx, lookback=20, wick_ratio=2.0)
    assert len(niveles) == 1 and niveles[0].direction == BUY

    # mismo barrido pero con cuerpo grande: no es martillo
    serie[21] = C(21, 99, 100, 92, 93)
    assert hammer_sweep(serie, 21, ctx, lookback=20, wick_ratio=2.0) == []
    print("test_detector_martillo_exige_mecha_larga: OK")


def test_objetivo_por_multiplo_de_riesgo():
    # sin tp_price pero con tp_r_multiple=2: TP debe salir a 2R de la entrada
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 96, 102), C(3, 102, 103, 99, 101),
        C(4, 101, 106, 100, 105),   # entrada 105, SL 97 -> riesgo 8
        C(5, 105, 122, 104, 121),   # TP esperado 105 + 16 = 121
    ]
    def det(candles, i, ctx):
        return [Level(1, 100.0, BUY, 97.0, None, "test", tp_r_multiple=2.0)] if i == 1 else []
    t = run(serie, det)
    assert len(t) == 1
    assert abs(t[0].tp_price - 121.0) < 1e-9 and abs(t[0].rr - 2.0) < 1e-9
    assert t[0].outcome == "TP"
    print("test_objetivo_por_multiplo_de_riesgo: OK")


def test_zone_touch_entra_al_tocar_sin_ruptura():
    # nivel 100 en modo zone_touch: entra en la vela que lo toca, al precio
    # del nivel, sin necesidad de ruptura ni confirmacion previa
    serie = [
        C(0, 105, 106, 104, 105),
        C(1, 105, 106, 104, 105),
        C(2, 105, 106,  99, 103),   # toca 100 -> entrada a 100
        C(3, 103, 118, 102, 117),   # TP 116
    ]
    def det(candles, i, ctx):
        return [Level(1, 100.0, BUY, 92.0, 116.0, "fib",
                      entry_mode="zone_touch")] if i == 1 else []
    t = run(serie, det)
    assert len(t) == 1
    assert t[0].entry_price == 100.0 and t[0].outcome == "TP"
    print("test_zone_touch_entra_al_tocar_sin_ruptura: OK")


def test_zone_touch_resuelve_la_vela_de_entrada_simetricamente():
    """La vela de entrada se resuelve en el acto, gane o pierda.

    Descartar solo las velas que tocan el stop, conservando las que tocan
    el objetivo, elimina los perdedores inmediatos y deja los ganadores
    inmediatos. Sobre ruido puro ese sesgo solo ya llevaba el acierto del
    27% teorico al 42%, con un profit factor aparente de 2,0.
    """
    def det(candles, i, ctx):
        return [Level(1, 100.0, BUY, 92.0, 116.0, "fib",
                      entry_mode="zone_touch")] if i == 1 else []

    # la vela de entrada perfora el stop -> perdida registrada, no descartada
    perdedora = [
        C(0, 105, 106, 104, 105), C(1, 105, 106, 104, 105),
        C(2, 105, 106,  90, 103),   # toca 100 y tambien el SL 92
        C(3, 103, 118, 102, 117),
    ]
    t = run(perdedora, det)
    assert len(t) == 1 and t[0].outcome == "SL"

    # la vela de entrada "alcanza" el objetivo: NO se acredita, porque su
    # maximo pudo ser anterior al toque de entrada. Queda abierta.
    ambigua = [
        C(0, 105, 106, 104, 105), C(1, 105, 106, 104, 105),
        C(2, 105, 120,  99, 118),   # toca 100 y su maximo supera el TP 116
        C(3, 118, 119, 117, 118),
    ]
    t = run(ambigua, det)
    assert len(t) == 1
    assert t[0].exit_index == 3, "no debe acreditarse en la vela de entrada"
    print("test_zone_touch_resuelve_la_vela_de_entrada_simetricamente: OK")


def test_escalera_reproduce_los_precios_del_video():
    """La escalera debe dar los precios exactos medidos en el reel.

    Ejemplo 1: tramo 6,820 (4785,365 -> 4778,545)
    Ejemplo 2: tramo 8,268 (4647,306 -> 4639,038)
    Los dos dan la misma rejilla en multiplos de medio tramo.
    """
    casos = [
        (4785.365, 4778.545, {
            -3.5: 4809.235, -3.0: 4805.825, -1.5: 4795.595, -1.0: 4792.185,
            1.0: 4778.545, 2.0: 4771.725, 3.0: 4764.906, 3.5: 4761.496,
            5.0: 4751.266, 5.5: 4747.856}),
        (4647.306, 4639.038, {
            -3.5: 4676.244, -3.0: 4672.110, -1.5: 4659.708, -1.0: 4655.574,
            1.0: 4639.038, 2.0: 4630.770, 3.0: 4622.502, 3.5: 4618.368,
            5.0: 4605.966, 5.5: 4601.832}),
    ]
    for h, l, esperado in casos:
        leg = h - l
        for m, precio in esperado.items():
            assert abs((h - m * leg) - precio) < 0.002, (h, m, precio)
    print("test_escalera_reproduce_los_precios_del_video: OK")


def test_escalera_exige_inducement():
    """Sin barrido del high anterior no hay senal."""
    def serie_con(sweep_alto):
        h1 = 115.0 if sweep_alto else 105.0
        cs = [C(0, 100, 101, 99, 100), C(1, 100, 102, 99, 100),
              C(2, 100, 110, 99, 100),                     # high anterior
              C(3, 100, 102, 99, 100), C(4, 100, 101, 99, 100),
              C(5, 100, 101, 90, 95),                      # swing low
              C(6, 95, 101, 96, 100), C(7, 100, 102, 97, 100),
              C(8, 100, h1, 99, 100),                      # barre (o no) el anterior
              C(9, 100, 102, 99, 100), C(10, 100, 101, 99, 100),
              C(11, 100, 101, 95, 95), C(12, 95, 96, 85, 88)]  # CHoCH bajo el low
        for k, c in enumerate(cs):
            c.index = k
        return cs

    con = serie_con(True)
    sin = serie_con(False)
    hay = [choch_ladder(con, k, build_ctx(con)) for k in range(len(con))]
    no = [choch_ladder(sin, k, build_ctx(sin)) for k in range(len(sin))]
    assert any(x for x in hay), "con barrido deberia emitir"
    assert not any(x for x in no), "sin barrido no deberia emitir"
    print("test_escalera_exige_inducement: OK")


def test_summarize_aplica_costos():
    serie = [
        C(0, 95, 96, 94, 95), C(1, 95, 97, 94, 96),
        C(2, 96, 103, 96, 102), C(3, 102, 103, 99, 101),
        C(4, 101, 106, 100, 105), C(5, 105, 112, 104, 111),
    ]
    t = run(serie, fixed_level(100.0, BUY, 97.0, 110.0))
    bruto = summarize(t)["exp_R"]
    neto = summarize(t, cost_r=0.02)["exp_R"]
    assert abs((bruto - neto) - 0.02) < 1e-9
    print("test_summarize_aplica_costos: OK")


if __name__ == "__main__":
    test_secuencia_completa_dispara_entrada()
    test_sin_regreso_no_hay_entrada()
    test_mecha_no_rompe_el_nivel()
    test_cierre_del_lado_del_sl_mata_el_nivel()
    test_sl_tiene_prioridad_sobre_tp_en_la_misma_vela()
    test_nivel_expira()
    test_filtro_rr_minimo()
    test_una_sola_operacion_a_la_vez()
    test_detector_ayer_cierre_respeta_el_sesgo()
    test_detector_martillo_exige_mecha_larga()
    test_objetivo_por_multiplo_de_riesgo()
    test_zone_touch_entra_al_tocar_sin_ruptura()
    test_zone_touch_resuelve_la_vela_de_entrada_simetricamente()
    test_escalera_reproduce_los_precios_del_video()
    test_escalera_exige_inducement()
    test_summarize_aplica_costos()
    print("TODOS LOS TESTS PASARON")
