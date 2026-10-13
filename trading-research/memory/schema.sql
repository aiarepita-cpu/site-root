-- Hypothesis ledger (Step 7 of the guide). One table.
CREATE TABLE IF NOT EXISTS hypotheses (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    idea                 TEXT NOT NULL,          -- one sentence
    source_agent         TEXT NOT NULL,
    market               TEXT NOT NULL,          -- e.g. "SPY,QQQ,IWM"
    date_tested          TEXT,                   -- ISO date of the latest test
    strategy_file        TEXT,                   -- strategies/<name>_v<N>.py
    strategy_version     INTEGER,
    variations_tried     INTEGER NOT NULL DEFAULT 0,  -- every backtest attempt counts (feeds the Deflated Sharpe)
    market_regime        TEXT CHECK (market_regime IN
                         ('trending up','trending down','choppy','high volatility')),
    backtest_result      TEXT,
    sealed_test_result   TEXT,                   -- the sealed period is used once per idea
    paper_trading_result TEXT,
    status               TEXT NOT NULL DEFAULT 'untested' CHECK (status IN
                         ('untested','failed','passed backtest only','passed paper','paused','retired')),
    lessons_learned      TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
