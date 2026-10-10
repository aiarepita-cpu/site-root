-- Hypothesis ledger
CREATE TABLE IF NOT EXISTS hypotheses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    title         TEXT NOT NULL,
    statement     TEXT NOT NULL,
    memo_path     TEXT,                 -- research/<file>.md
    status        TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open','testing','rejected','supported','retired')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id INTEGER NOT NULL REFERENCES hypotheses(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    kind          TEXT NOT NULL CHECK (kind IN ('backtest','paper_trade','research','note')),
    strategy      TEXT,                 -- e.g. mean_reversion_v1
    ref_path      TEXT,                 -- backtests/... or journal/...
    summary       TEXT NOT NULL,
    supports      INTEGER CHECK (supports IN (-1,0,1))  -- against / neutral / for
);
