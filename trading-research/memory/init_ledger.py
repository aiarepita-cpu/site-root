"""Create memory/ledger.db from memory/schema.sql. Safe to re-run."""
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent

with sqlite3.connect(HERE / "ledger.db") as conn:
    conn.executescript((HERE / "schema.sql").read_text())
print(f"Ledger ready at {HERE / 'ledger.db'}")
