"""Telegram notifications (one-way). Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the
environment (or config/.env). The token is never printed. Missing settings never break a run.

    python3 -m src.notify --chat-ids             # after you message the bot once: list chat ids
    python3 -m src.notify --journal 2026-10-14   # send that day's paper-trading decisions
    python3 -m src.notify --file journal/review-2026-10-18.md
    python3 -m src.notify --text "hello"
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.telegram.org/bot{token}/{method}"
LIMIT = 4000  # Telegram max is 4096 characters per message


def _settings():
    load_dotenv(ROOT / "config" / ".env", override=False)
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(), os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def _call(token, method, params, opener=urllib.request.urlopen):
    req = urllib.request.Request(API.format(token=token, method=method),
                                 data=urllib.parse.urlencode(params).encode())
    try:
        with opener(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001 - never leak the token via the URL in the error
        return {"ok": False, "description": type(e).__name__}


def chunks(text, limit=LIMIT):
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        while len(cur) + len(line) > limit and len(line) > limit:
            room = limit - len(cur)
            out.append(cur + line[:room])
            cur, line = "", line[room:]
        if len(cur) + len(line) > limit:
            out.append(cur)
            cur = ""
        cur += line
    if cur:
        out.append(cur)
    return out


def send(text, opener=urllib.request.urlopen) -> tuple[bool, str]:
    token, chat = _settings()
    if not token or not chat:
        return False, "Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing); nothing sent."
    for part in chunks(text):
        r = _call(token, "sendMessage", {"chat_id": chat, "text": part, "disable_web_page_preview": "true"}, opener)
        if not r.get("ok"):
            return False, f"Telegram error: {r.get('description', 'unknown')}"
    return True, "sent"


def chat_ids(opener=urllib.request.urlopen):
    token, _ = _settings()
    if not token:
        return None
    r = _call(token, "getUpdates", {}, opener)
    seen = {}
    for u in r.get("result", []):
        chat = (u.get("message") or u.get("my_chat_member") or {}).get("chat")
        if chat:
            seen[chat["id"]] = chat.get("username") or chat.get("title") or chat.get("first_name") or ""
    return seen


def journal_summary(day: str, journal_dir=ROOT / "journal") -> str:
    path = Path(journal_dir) / "decisions.jsonl"
    entries = []
    if path.exists():
        entries = [e for e in map(json.loads, path.read_text().splitlines()) if e["timestamp"].startswith(day)]
    if not entries:
        return f"Paper trading {day}: no decisions journaled."
    lines = [f"Paper trading {day} (PAPER, not real money)"]
    for e in entries:
        o = e.get("order") or {}
        sym = o.get("symbol") or (e.get("market_conditions") or {}).get("symbol") or ""
        qty = f" {o['qty']}" if o.get("qty") else ""
        line = f"- {e['strategy']} v{e['version']}: {e['decision']} {sym}{qty}".rstrip()
        if e["decision"] in ("BLOCKED", "ERROR", "SKIPPED"):
            line += f" | {e.get('risk_check') or e['reasoning']}"
        lines.append(line)
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--chat-ids", action="store_true")
    g.add_argument("--journal", nargs="?", const=date.today().isoformat())
    g.add_argument("--file")
    g.add_argument("--text")
    a = p.parse_args()
    if a.chat_ids:
        ids = chat_ids()
        print("TELEGRAM_BOT_TOKEN missing" if ids is None else (ids or "No chats yet: send /start to the bot first."))
        return
    text = a.text or (Path(a.file).read_text() if a.file else journal_summary(a.journal))
    ok, msg = send(text)
    print(msg)
    sys.exit(0)  # a failed notification must never fail the trading run


if __name__ == "__main__":
    main()
