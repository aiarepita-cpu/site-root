"""Decision journal. One entry per decision, including holds, skips and blocked orders.

Writes journal/YYYY-MM-DD.md (for people) and journal/decisions.jsonl (for the Critic).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

JOURNAL_DIR = Path(__file__).resolve().parents[1] / "journal"
DECISIONS = ("BUY", "SELL", "HOLD", "BLOCKED", "SKIPPED", "ERROR")


def log_decision(strategy: str, version, decision: str, reasoning: str,
                 market_conditions: dict, risk_check: str = None, order: dict = None,
                 order_id: str = None, now: datetime = None, journal_dir: Path = None) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    now = now or datetime.now(timezone.utc)
    d = Path(journal_dir or JOURNAL_DIR)
    d.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": now.isoformat(timespec="seconds"),
        "strategy": strategy,
        "version": version,
        "decision": decision,
        "reasoning": reasoning,
        "market_conditions": market_conditions,
        "risk_check": risk_check,
        "order": order,
        "order_id": order_id,
    }
    with open(d / "decisions.jsonl", "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    conds = ", ".join(f"{k}={v}" for k, v in market_conditions.items()) or "n/a"
    lines = [
        f"## {entry['timestamp']} | {strategy} v{version} | {decision}",
        f"- Market conditions: {conds}",
        f"- Reasoning: {reasoning}",
    ]
    if order:
        lines.append(f"- Order: {order}")
    if risk_check:
        lines.append(f"- Risk check: {risk_check}")
    if order_id:
        lines.append(f"- Alpaca paper order id: {order_id}")
    with open(d / f"{now.date().isoformat()}.md", "a") as f:
        f.write("\n".join(lines) + "\n\n")
    return entry
