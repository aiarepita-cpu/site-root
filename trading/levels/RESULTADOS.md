# Resultados — motor de niveles (9 reels de @asimetricos_marrow)

## Qué se construyó

Los 9 reels comparten una sola mecánica y se diferencian solo en de dónde sale
el nivel. El motor implementa esa mecánica una vez:

1. un detector publica un **nivel**
2. el precio lo **rompe con CUERPO** (*"la mecha no cuenta"*, literal en 5 de 9)
3. el precio **regresa** al nivel (*"ahí compran casi todos"* — no se entra en la ruptura)
4. una vela **confirma** cerrando de nuevo con cuerpo del lado de la ruptura
5. **SL** del otro lado del nivel, **TP** en el extremo previo

Seis detectores intercambiables producen los niveles. 12 tests, backtest de
78.000 velas en 8 segundos.

## Fallas corregidas durante la construcción

| Falla | Impacto | Corrección |
|---|---|---|
| `trendline` y `hombro` recalculaban todos los pivotes fractales en cada barra | O(n²): el backtest no terminaba | Pivotes y límites de sesión precomputados una vez en `Ctx`, consulta O(1) |
| `trendline` reemitía su nivel en cada barra | Miles de niveles duplicados vivos | Solo emite cuando se confirma un pivote nuevo |
| `rango_sesion` fijaba `tp_price=None` | No generaba ni una operación | Añadido `tp_r_multiple` para los reels que apuntan "al doble" del riesgo |

## Resultados

Configuración idéntica en todos los casos. Sin ajustar un solo parámetro entre
activos ni entre períodos.

| Detector | Desarrollo 09-22 | | Holdout oro 23-26 | | Cruzado 5 activos | |
|---|---:|---:|---:|---:|---:|---:|
| | **expR** | **PF** | **expR** | **PF** | **expR** | **PF** |
| ayer_cierre | −0,105 | 0,77 | −0,090 | 0,80 | +0,001 | 1,00 |
| trendline | −0,058 | 0,92 | −0,441 | 0,43 | −0,101 | 0,85 |
| martillo | +0,034 | 1,04 | −0,247 | 0,71 | +0,172 | 1,22 |
| hombro | −0,076 | 0,89 | +0,022 | 1,03 | −0,059 | 0,91 |
| **barrido_diario** | **+0,195** | **1,27** | **−0,183** | **0,76** | **−0,088** | **0,88** |
| rango_sesion | +0,022 | 1,03 | +0,130 | 1,21 | −0,082 | 0,88 |

**Ningún detector es positivo en las tres columnas.**

## El caso `barrido_diario`

Es el que más prometía y merece el detalle, porque es el patrón exacto que
veníamos evitando.

En desarrollo: 924 operaciones, expectancy +0,195R, PF 1,27, bootstrap de 10.000
remuestreos con IC 95% [+0,046, +0,349] y P(expectancy ≤ 0) = 0,0035.

Tres motivos para no creerle, detectados **antes** de mirar el holdout:

1. **Concentración extrema.** Las 10 mejores operaciones aportan el 65% del
   resultado; más allá de las 25 mejores, el conjunto es negativo. Con esa
   asimetría el t-test no aplica.
2. **Sensibilidad no monótona al tope de R:R.** El IC inferior es negativo con
   topes de 1, 2, 3 y 8, y positivo solo en 5 y 20. Un parámetro sano no se
   comporta así.
3. **Costos.** Riesgo mediano de $4,10 por operación. Con spread de $0,25 el
   costo es 0,082R y el IC 95% ya incluye el cero.

Y después, las dos pruebas fuera de muestra:

- **Holdout oro 2023-2026**: expectancy **−0,183R**, PF 0,76 sobre 240 operaciones
- **Cruzado (5 activos, 835 operaciones)**: expectancy **−0,088R**, negativo en 4 de 5

El signo se invierte por completo en ambas. Es la misma firma que la asimetría
BUY/SELL del proyecto anterior: significativa en muestra, invertida fuera de ella.

## Conclusión

Las estrategias del canal, mecanizadas y medidas con el mismo rigor, **no
muestran edge aplicable**. El motor funciona, está testeado y es rápido; lo que
no aparece es la ventaja.

`martillo` es lo único que queda vivo (positivo en desarrollo y en cruzado,
negativo en el holdout de oro). No alcanza para operarlo, pero es el único que
justificaría una prueba más con datos frescos e independientes.


---

# Anexo — Estrategia Fibonacci (reel DdyNFhCohRO, otro creador)

## Reglas extraídas

XAUUSD. Tras un **CHoCH**, trazar Fibonacci sobre el tramo que lo produjo;
comprar al retroceder a la **golden zone (0,5–0,618)**, stop debajo del 0,786,
objetivo en la extensión **1,272**. El R:R queda fijado por la geometría en
**2,699** (premio 0,772·tramo / riesgo 0,286·tramo), con punto de equilibrio
teórico en 27,0% de acierto.

## Por qué este caso importa más que el resultado

La primera medición dio **PF 1,79 en desarrollo, 1,55 en holdout y 1,64 cruzado
en 5 activos**. Siete conjuntos independientes, todos espectaculares. Era falso.

Lo delató un **control sobre ruido**: correr el detector sobre caminatas
aleatorias, donde ninguna estrategia puede tener ventaja. Daba PF 2,02 — mejor
que sobre datos reales. Eso prueba bug, no edge.

### Dos bugs encontrados

1. **Selección asimétrica en la vela de entrada.** Si esa vela tocaba el stop,
   descartaba la operación entera; si tocaba el objetivo, la conservaba.
   Eliminaba perdedores inmediatos y guardaba ganadores inmediatos. Sobre ruido,
   eso solo llevaba el acierto del 27% teórico al **42%**.
2. **Objetivo acreditado con el máximo de la vela de entrada.** En una compra se
   entra en el mínimo de la vela, y su máximo suele ser *anterior* al toque:
   cobraba ganancias que no pudieron ocurrir. Añadía otros ~5 puntos.

### El punto de comparación correcto

Ya corregido, el motor da **31%** sobre ruido en vez del 27% teórico. No es un
bug: simular órdenes límite con velas concede un llenado favorable (se entra en
el mínimo y la vela cierra más arriba). La consecuencia metodológica es que
**el patrón de referencia no es el 27% teórico sino un control con niveles
aleatorios**, misma geometría y mismo motor.

## Resultado final

| Conjunto | Fib: n | acierto | expR | Aleatorio: expR | Diferencia |
|---|---:|---:|---:|---:|---:|
| Desarrollo 09-22 | 5336 | 21,4% | −0,208 | −0,088 | −0,120 |
| Holdout 23-26 | 1457 | 19,8% | −0,266 | −0,020 | −0,246 |
| EURUSD | 1015 | 19,9% | −0,264 | −0,017 | −0,247 |
| GBPUSD | 1255 | 19,3% | −0,287 | −0,279 | −0,008 |
| USDJPY | 1102 | 22,1% | −0,181 | −0,058 | −0,123 |
| AUDUSD | 1198 | 22,0% | −0,185 | +0,009 | −0,194 |
| Plata | 849 | 23,6% | −0,129 | −0,167 | +0,038 |
| **Agregado** | **12212** | **21,2%** | **−0,217** | **−0,085** | **−0,132** |

IC 95% Fibonacci [−0,244, −0,191] · IC 95% aleatorio [−0,147, −0,024]. **No se
solapan.**

La estrategia no solo pierde: pierde **significativamente más que poner los
niveles al azar**. Con 21,2% de acierto contra un equilibrio de 27,0%, queda casi
6 puntos por debajo de lo necesario.

Los 6 detectores del canal anterior usan modo `break_return` (entrada al cierre
de la vela) y no estaban afectados por estos bugs: sus cifras no cambiaron.

---

# Anexo — Auditoría del control de ruido

El control encontró dos bugs reales, ambos en el propio control, y dejó un
residuo sin explicar. Conviene registrar las tres cosas.

## Bug 1 — el generador no era una caminata

Sorteaba los subpasos de cada vela desde la APERTURA en vez de desde el
subpaso anterior. Dentro de la barra el precio revertía a la apertura, las
mechas se inflaban y se retraían, y la barrera más cercana se tocaba de más.
Con el stop a 1R, todo detector con objetivo lejano perdía sistemáticamente:
hasta −0,27R, que parecía un sesgo pesimista del motor.

Lo delataron dos señales. `--intrabar tp` daba cifras idénticas al dígito, o
sea que la ambigüedad intrabarra no ocurría nunca y la primera explicación era
falsa; y el signo del sesgo seguía al R:P. Corregido con subpasos acumulados.

## Bug 2 — la resolución intrabarra fabricaba sesgo

Con 12 subpasos, `barrido_diario` daba +0,104 sobre ruido. Con 48, +0,008. Era
discretización: el camino se asoma más allá de una barrera entre subpasos y no
queda registrado, y la barrera cercana se aproxima mucho más seguido que el
objetivo.

Hay una tensión de calibración que no se resuelve con una caminata simple: el
oro real tiene rango/volatilidad 1,274 y un browniano continuo 1,596. Doce
subpasos aciertan la forma de la vela real pero resuelven mal las barreras;
192 resuelven bien pero dan velas más anchas. Para detectar bugs manda la
limpieza mecánica: resolución alta, y leer contra el control, no contra cero.

## El residuo de `hombro`, sin explicar

Queda +0,0251R sobre ruido, IC95 [+0,0073, +0,0429] sobre 36.877 operaciones
(medición única preregistrada, semillas nunca usadas). Todos los componentes
verifican limpio:

| verificación | resultado |
|---|---|
| resolución operación por operación contra replay independiente | 0 errores en 18.873 |
| decisión de entrada reproducible truncando la serie en la entrada | 400/400 |
| barreras con origen en velas previas | 0 violaciones |
| entrada igual al cierre de su barra | 0 violaciones |
| caminata aritmética (martingala exacta) vs geométrica | idénticas |
| geometría fija, R:P de 1 a 8 | ≤0,28σ del equilibrio 1/(1+rr) |
| continuación fresca e independiente | +0,0099, cero adentro |
| bootstrap independiente vs por bloques | mismo ancho |

Cinco hipótesis cayeron: mechas espurias, amplificación por R:P, intervalo
subestimado por autocorrelación, convexidad log/lineal, e información futura.

Dos advertencias sobre este número. Se midió unas ocho veces con distintas
semillas antes de preregistrar, y la magnitud cayó de +0,086 a +0,025 al
triplicar la muestra y quitar la selección: es la firma de la maldición del
ganador. Y el control de la medición final quedó en R:P 1,85 contra 2,98 de
`hombro`, porque en modo `break_return` la entrada no es en el cierre de la
barra del nivel sino en el de una confirmación posterior.

**Consecuencia práctica.** El residuo es la octava parte de los efectos que se
miden sobre datos reales, y `--comparar` lo neutraliza: mide cada detector
contra SU PROPIO ruido emparejado por cubo de R:P, así que lo resta sea cual
sea su origen. Con esa corrección, `hombro` sobre datos reales da peor que su
propio ruido en desarrollo (−0,170) y en cruzado (−0,150).

## Corrección a la conclusión sobre Fibonacci

Arriba se afirma que Fibonacci "pierde significativamente más que poner los
niveles al azar". **Esa comparación era inválida**: contrastaba una estrategia
de orden límite con R:P 2,70 contra un control de entrada al cierre con R:P
1,21, con modo de entrada distinto. Contra su propio ruido emparejado por R:P,
Fibonacci sale MEJOR que su línea base en desarrollo (+0,079R) y en cruzado
(+0,073R), e indistinguible en holdout.

Eso tampoco la salva: su línea base es −0,2865R, y ese número es el costo de
la regla conservadora de la vela del toque, no una propiedad del mercado. Su
expectativa absoluta sigue siendo −0,21R.
