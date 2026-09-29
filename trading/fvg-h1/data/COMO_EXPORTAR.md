# Cómo exportar M15 desde MT5

Dejá el archivo en `trading/fvg-h1/data/XAUUSD_M15.csv`.

## Pasos en MetaTrader 5

1. **Herramientas → Opciones → Gráficos**: subí "Máximas barras en el gráfico"
   a `99999999`. Si no, MT5 recorta el historial al exportar.
2. **Ver → Símbolos** (Ctrl+U) → buscá XAUUSD → pestaña **Barras** → elegí
   período **M15** → **Solicitar**. Poné la fecha de inicio en 2009 o antes;
   si el bróker no llega tan atrás, traé todo lo que tenga.
3. **Exportar barras** → guardalo como CSV.

## Formato

Sirve tal como sale de MT5, con tabuladores y la fecha partida en dos
columnas. No hace falta tocarlo:

```
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>
2024.01.02	00:00:00	2062.94	2064.31	2062.10	2063.55	412	0	28
```

También sirve el formato simple separado por comas:

```
timestamp,open,high,low,close
2024-01-02 00:00:00,2062.94,2064.31,2062.10,2063.55
```

Mirá `EJEMPLO_formato_MT5.csv` en esta carpeta para comparar.

## Qué hace falta que tenga

- **Rango**: cuanto más largo mejor. Con 2009 en adelante se conserva el corte
  de holdout en 2023 que usa todo el proyecto. Si el bróker solo da unos pocos
  años, igual sirve, pero el corte hay que recalcularlo.
- **Continuidad**: los huecos de fin de semana son normales. Un salto grande de
  precio en una fecha suelta suele ser un cambio de contrato o de fuente, y
  contamina el backtest; se detecta y se avisa antes de medir.
- **Columna SPREAD**: si viene, mejor. Permite usar el costo real por vela en
  vez de estimarlo, y en M15 el costo pesa el doble que en H1.

## Por qué M15

En H1 la escalera da 447 operaciones en desarrollo. El umbral de detección
(80% de potencia) es 0,265R y el de rentabilidad 0,078R: toda ventaja plausible
cae en el medio, o sea rentable pero indetectable.

En M15 se esperan ~1.800 operaciones. La detección baja a 0,132R y la
rentabilidad sube a 0,157R por el spread. El orden se invierte, y recién ahí un
resultado negativo significa algo: que no hay ventaja operable, en vez de que
faltan datos.
