import io
import json
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from src import notify


class FakeOpener:
    def __init__(self, reply=None):
        self.calls, self.reply = [], reply or {"ok": True, "result": []}

    def __call__(self, req, timeout):
        self.calls.append((req.full_url, dict(urllib.parse.parse_qsl(req.data.decode()))))
        return io.BytesIO(json.dumps(self.reply).encode())


ENV = {"TELEGRAM_BOT_TOKEN": "123:SECRET", "TELEGRAM_CHAT_ID": "42"}


class Notify(unittest.TestCase):
    @mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""})
    def test_missing_config_sends_nothing(self):
        op = FakeOpener()
        ok, msg = notify.send("hi", opener=op)
        self.assertFalse(ok)
        self.assertEqual(op.calls, [])

    @mock.patch.dict(os.environ, ENV)
    def test_sends_to_chat(self):
        op = FakeOpener()
        self.assertEqual(notify.send("hi", opener=op), (True, "sent"))
        url, data = op.calls[0]
        self.assertTrue(url.endswith("/sendMessage"))
        self.assertEqual((data["chat_id"], data["text"]), ("42", "hi"))

    @mock.patch.dict(os.environ, ENV)
    def test_errors_never_include_token(self):
        def boom(req, timeout):
            raise OSError(f"failed {req.full_url}")
        ok, msg = notify.send("hi", opener=boom)
        self.assertFalse(ok)
        self.assertNotIn("SECRET", msg)

    @mock.patch.dict(os.environ, ENV)
    def test_long_text_split_under_limit(self):
        op = FakeOpener()
        notify.send("x" * 50 + "\n" + "y" * 9000, opener=op)
        self.assertGreaterEqual(len(op.calls), 3)
        self.assertTrue(all(len(d["text"]) <= notify.LIMIT for _, d in op.calls))
        self.assertEqual("".join(d["text"] for _, d in op.calls), "x" * 50 + "\n" + "y" * 9000)

    @mock.patch.dict(os.environ, ENV)
    def test_chat_ids(self):
        op = FakeOpener({"ok": True, "result": [{"message": {"chat": {"id": 7, "username": "luis"}}}]})
        self.assertEqual(notify.chat_ids(opener=op), {7: "luis"})

    def test_journal_summary(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [
                {"timestamp": "2026-10-14T12:52:00+00:00", "strategy": "trend_filter_200", "version": 1,
                 "decision": "BUY", "order": {"symbol": "QQQ", "qty": 50}, "reasoning": "Entry."},
                {"timestamp": "2026-10-14T12:52:00+00:00", "strategy": "trend_filter_200", "version": 1,
                 "decision": "BLOCKED", "order": {"symbol": "IWM", "qty": 10},
                 "risk_check": "Max drawdown hit. Trading stopped.", "reasoning": "Entry."},
                {"timestamp": "2026-10-13T12:52:00+00:00", "strategy": "x", "version": 1,
                 "decision": "BUY", "order": {"symbol": "SPY", "qty": 1}, "reasoning": "old"},
            ]
            Path(d, "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
            s = notify.journal_summary("2026-10-14", journal_dir=d)
            self.assertIn("BUY QQQ 50", s)
            self.assertIn("BLOCKED IWM 10 | Max drawdown hit", s)
            self.assertNotIn("SPY", s)
            self.assertIn("no decisions", notify.journal_summary("2026-10-15", journal_dir=d))


if __name__ == "__main__":
    unittest.main()
