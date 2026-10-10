"""Hypothesis ledger helper. Every agent searches here before proposing an idea.

CLI:
    python3 memory/ledger.py search [--market SPY] [--regime choppy] [--status failed]
"""
import argparse
import sqlite3
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "ledger.db"

STATUSES = ("untested", "failed", "passed backtest only", "passed paper", "paused", "retired")
REGIMES = ("trending up", "trending down", "choppy", "high volatility")
_UPDATABLE = {
    "idea", "date_tested", "strategy_file", "strategy_version", "market_regime",
    "backtest_result", "sealed_test_result", "paper_trading_result", "status",
}


def connect(db_path=DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript((HERE / "schema.sql").read_text())
    return conn


def search(conn, market=None, regime=None, status=None):
    """Past ideas filtered by market (substring match), regime and status."""
    sql, args = "SELECT * FROM hypotheses WHERE 1=1", []
    if market:
        sql += " AND market LIKE ?"
        args.append(f"%{market}%")
    if regime:
        sql += " AND market_regime = ?"
        args.append(regime)
    if status:
        sql += " AND status = ?"
        args.append(status)
    return [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]


def add(conn, idea, source_agent, market, **fields) -> int:
    cur = conn.execute(
        "INSERT INTO hypotheses (idea, source_agent, market) VALUES (?, ?, ?)",
        (idea, source_agent, market),
    )
    hid = cur.lastrowid
    if fields:
        update(conn, hid, **fields)
    conn.commit()
    return hid


def update(conn, hid, **fields):
    bad = set(fields) - _UPDATABLE
    if bad:
        raise ValueError(f"Not updatable: {sorted(bad)}")
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE hypotheses SET {cols}, updated_at = datetime('now') WHERE id = ?",
        (*fields.values(), hid),
    )
    conn.commit()


def add_lesson(conn, hid, lesson: str):
    """Append a lesson; never overwrites earlier ones."""
    conn.execute(
        "UPDATE hypotheses SET lessons_learned = "
        "COALESCE(lessons_learned || char(10), '') || ?, updated_at = datetime('now') WHERE id = ?",
        (f"[{date.today().isoformat()}] {lesson}", hid),
    )
    conn.commit()


def record_backtest(conn, hid, result: str, status: str, regime=None, tested_on=None):
    """Call after EVERY backtest attempt: counts the variation and stores the result."""
    conn.execute(
        "UPDATE hypotheses SET variations_tried = variations_tried + 1 WHERE id = ?", (hid,)
    )
    fields = {"backtest_result": result, "status": status,
              "date_tested": (tested_on or date.today()).isoformat()}
    if regime:
        fields["market_regime"] = regime
    update(conn, hid, **fields)


def record_paper_review(conn, hid, result: str, status=None):
    fields = {"paper_trading_result": result}
    if status:
        fields["status"] = status
    update(conn, hid, **fields)


def eligible_for_paper(conn):
    """Only ideas that passed the backtest, including the one sealed-period run."""
    return [r for r in search(conn)
            if r["status"] in ("passed backtest only", "passed paper") and r["sealed_test_result"]]


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--market")
    s.add_argument("--regime", choices=REGIMES)
    s.add_argument("--status", choices=STATUSES)
    a = p.parse_args()
    with connect() as conn:
        for r in search(conn, a.market, a.regime, a.status):
            print(f"#{r['id']} [{r['status']}] {r['market']} | {r['strategy_file']} "
                  f"v{r['strategy_version']} | variations={r['variations_tried']} | {r['idea']}")


if __name__ == "__main__":
    main()
