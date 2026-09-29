import csv
import io
from dataclasses import dataclass
from datetime import datetime

_TS_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d",
)


@dataclass
class Candle:
    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)


def _parse_ts(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"timestamp no reconocido: {raw!r}")


def _abrir(path: str):
    """Devuelve el texto del archivo, sea UTF-8 o UTF-16 (MT5 exporta UTF-16)."""
    crudo = open(path, "rb").read()
    for bom, enc in ((b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"),
                     (b"\xef\xbb\xbf", "utf-8-sig")):
        if crudo.startswith(bom):
            return crudo.decode(enc)
    return crudo.decode("utf-8", errors="replace")


_COLS_SIN_CABECERA = ("timestamp", "open", "high", "low", "close")


def load_csv(path: str) -> list[Candle]:
    """Carga un CSV OHLC.

    Acepta el formato propio (`timestamp,open,high,low,close`), la exportacion
    NATIVA de MetaTrader 5 con tabuladores y la fecha partida en `<DATE>` y
    `<TIME>`, y tambien la variante SIN CABECERA que produce el boton
    "Exportar barras" de la ventana de simbolos:

        2022.06.28 14:15,1822.68,1823.47,1820.38,1823.34,1068,0

    Ademas detecta UTF-16, que es lo que escribe MT5. Asi el archivo se usa
    tal como sale, sin convertirlo a mano.
    """
    texto = _abrir(path)
    primera = texto.split("\n", 1)[0]
    sep = "\t" if primera.count("\t") >= 3 else ","

    # sin cabecera: el primer campo ya es una fecha
    tiene_cabecera = True
    try:
        _parse_ts(primera.split(sep)[0])
        tiene_cabecera = False
    except ValueError:
        pass

    f = io.StringIO(texto)
    if tiene_cabecera:
        reader = csv.DictReader(f, delimiter=sep)
        campos = reader.fieldnames
        cols = {c.lower().strip().strip("<>"): c for c in campos}

        def col(*names: str, req: bool = True) -> str | None:
            for n in names:
                if n in cols:
                    return cols[n]
            if req:
                raise KeyError(f"falta alguna de {names} en {campos}")
            return None

        fecha_c = col("timestamp", "date", "datetime")
        hora_c = col("time", req=False)          # MT5: la hora en su columna
        if hora_c == fecha_c:
            hora_c = None
        o_c, h_c, l_c, c_c = col("open"), col("high"), col("low"), col("close")
    else:
        reader = csv.DictReader(f, delimiter=sep,
                                fieldnames=list(_COLS_SIN_CABECERA))
        fecha_c, hora_c = "timestamp", None
        o_c, h_c, l_c, c_c = "open", "high", "low", "close"

    out: list[Candle] = []
    for row in reader:
        if not row.get(fecha_c):
            continue
        crudo = row[fecha_c]
        if hora_c is not None and row.get(hora_c):
            crudo = f"{crudo.strip()} {row[hora_c].strip()}"
        out.append(Candle(0, _parse_ts(crudo), float(row[o_c]),
                          float(row[h_c]), float(row[l_c]), float(row[c_c])))
    out.sort(key=lambda c: c.timestamp)
    for i, c in enumerate(out):
        c.index = i
    return out
