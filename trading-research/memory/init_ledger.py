"""Create memory/ledger.db from memory/schema.sql. Safe to re-run."""
from ledger import DB_PATH, connect

connect().close()
print(f"Ledger ready at {DB_PATH}")
