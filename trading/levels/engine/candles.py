import csv
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


def load_csv(path: str) -> list[Candle]:
    """Carga un CSV OHLC.

    Acepta tanto el formato propio (`timestamp,open,high,low,close`) como la
    exportacion NATIVA de MetaTrader 5, que viene con tabuladores, cabeceras
    entre angulos y la fecha partida en dos columnas:

        <DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
        2009.08.25\t22:00:00\t945.03\t945.08\t944.19\t944.24\t...

    Asi el archivo que sale de MT5 se usa sin tocarlo.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        cabecera = f.readline()
        f.seek(0)
        sep = "\t" if cabecera.count("\t") >= 3 else ","
        reader = csv.DictReader(f, delimiter=sep)
        cols = {c.lower().strip().strip("<>"): c for c in reader.fieldnames}

        def col(*names: str, req: bool = True) -> str | None:
            for n in names:
                if n in cols:
                    return cols[n]
            if req:
                raise KeyError(f"falta alguna de {names} en {reader.fieldnames}")
            return None

        fecha_c = col("timestamp", "date", "datetime")
        # MT5 nativo: la hora va en su propia columna
        hora_c = col("time", req=False)
        if hora_c is not None and hora_c == fecha_c:
            hora_c = None
        o_c, h_c, l_c, c_c = col("open"), col("high"), col("low"), col("close")

        out: list[Candle] = []
        for row in reader:
            crudo = row[fecha_c]
            if hora_c is not None and row.get(hora_c):
                crudo = f"{crudo.strip()} {row[hora_c].strip()}"
            out.append(Candle(0, _parse_ts(crudo), float(row[o_c]),
                              float(row[h_c]), float(row[l_c]), float(row[c_c])))
    out.sort(key=lambda c: c.timestamp)
    for i, c in enumerate(out):
        c.index = i
    return out
