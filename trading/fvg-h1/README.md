# FVG H1 — motor de backtest

Estrategia (XAUUSD, H1):

1. **Tendencia**: BOS/CHoCH causal. Swing high/low = fractal de 3 velas
   (1 vecino a cada lado), confirmado 1 vela después de formarse. El
   cierre de una vela por encima del último swing high confirmado =
   tendencia alcista; por debajo del último swing low = bajista.
2. **FVG**: patrón ICT de 3 velas. Alcista si `vela1.high < vela3.low`;
   bajista si `vela1.low > vela3.high`. Solo se crea si coincide con la
   tendencia vigente en ese momento.
3. **SL**: mecha del swing que originó **todo el tramo (leg) actual**,
   no solo el retroceso inmediato de este FVG puntual. Ese origen se fija
   una sola vez, en el CHoCH que invierte la tendencia (swing low si pasa
   a alcista, swing high si pasa a bajista), y se mantiene igual para
   todos los FVG que se formen dentro del mismo tramo — incluso después
   de BOS de continuación que rompen máximos/mínimos más nuevos. Solo se
   reemplaza en el próximo CHoCH (cambio real de tendencia). Si todavía
   no hay un swing de ese tipo confirmado (arranque de los datos), se usa
   como respaldo la mecha de la propia vela que originó el FVG.
4. **Invalidación**: cualquier mecha que toque/cruce el borde lejano del
   FVG (el límite del lado de `vela1`) lo descarta por completo, sin
   entrada.
5. **Entrada**: primero el precio debe tocar el FVG (mecha dentro del
   rango). Luego, la primera vela cuyo rango completo (mecha incluida)
   cierra totalmente fuera del FVG en el sentido favorable dispara la
   entrada, al precio de cierre de esa vela.
6. **TP**: cuerpo (máx/mín de open-close, no la mecha) del swing opuesto
   más cercano y ya confirmado antes de la entrada — swing high para
   compras, swing low para ventas.
7. **Filtro R:R**: si `reward/risk < 0.3`, la operación se cancela por
   completo (no se toma, no se busca otro swing).
8. Una sola operación abierta a la vez; cada FVG se resuelve una única
   vez (entra, se invalida, o se cancela).

## Supuesto de modelado (no es parte de la estrategia, es una limitación
de los datos OHLC): si en una misma vela el rango toca SL y TP a la vez,
no hay forma de saber cuál ocurrió primero solo con OHLC. Se asume SL
primero (peor caso). Esto puede subestimar el win rate real; para
eliminar esta ambigüedad haría falta backtestear con datos de menor
temporalidad (M1) dentro de cada vela H1.

## Uso

```bash
python3 tests/test_engine.py        # regresión (sin datos externos)
python3 run_backtest.py data/XAUUSD_H1.csv
```

CSV esperado: columnas `timestamp,open,high,low,close` (nombres de
columna flexibles, ver `engine/data_loader.py`).

## Pendiente

No hay salida de red permitida en este entorno hacia fuentes de datos
históricos (Yahoo Finance, Dukascopy, Stooq, etc.). Para correr el
backtest con datos reales:
- Habilitar esos dominios en la configuración de red del entorno, o
- Subir un CSV con velas H1 de XAUUSD a `data/`.
