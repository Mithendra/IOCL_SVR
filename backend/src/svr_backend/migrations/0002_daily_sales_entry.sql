-- 0002_daily_sales_entry.sql - the Daily Sales Entry module (SDD 5.4 / 9).
--
-- Storage shape: the full section 1-7 form is kept as a JSON `payload` (variable-
-- length repeating sections - credit cards, new credits, old credits, extra oil
-- items - map cleanly to JSON and the SDD leaves this table's normalization open,
-- 8.5). Scalars needed for indexing, carry-forward, and reporting are promoted to
-- real columns. `result` caches the calculation-engine output at save time.

CREATE TABLE daily_sales_entry (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_date            TEXT NOT NULL,                 -- YYYY-MM-DD
    pump_serial           TEXT NOT NULL,                 -- e.g. '12BC4523V-RD'
    submitted_by          TEXT NOT NULL,                 -- users.login_name
    entry_mode            TEXT NOT NULL DEFAULT 'manual'
                          CHECK (entry_mode IN ('manual', 'ocr', 'excel')),

    -- Carry-forward anchors (SDD 7.7). *_last is authoritative once saved.
    hs_current            REAL,
    ms_current            REAL,
    hs_last               REAL,
    ms_last               REAL,

    -- Rates locked onto the record at create time (SDD 19 item 7).
    sell_rate_hs          REAL,
    sell_rate_ms          REAL,
    oil_rates_json        TEXT,                          -- {"oil1": 62.0, ...}

    -- Cached engine output for fast reporting (recomputed on every write).
    gas_total             REAL,
    oil_total             REAL,
    expenses_total        REAL,
    net_bal_hand_off      REAL,

    payload               TEXT NOT NULL,                 -- full section 1-7 input, JSON
    result                TEXT NOT NULL,                 -- calculation-engine output, JSON

    last_updated_by       TEXT,
    last_updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Indexes per SDD 8.3: every daily table gets (date); (date, submitted_by) where
-- RBAC / reports filter on both; (pump_serial, shift_date) drives carry-forward.
CREATE INDEX idx_dse_shift_date ON daily_sales_entry (shift_date);
CREATE INDEX idx_dse_date_submitter ON daily_sales_entry (shift_date, submitted_by);
CREATE INDEX idx_dse_pump_date ON daily_sales_entry (pump_serial, shift_date);

-- daily_sales_summary - STUB (SDD 5.23-5.25). Combines the Off + Road submissions
-- and gates the Trial Balance upload until both are verified. Wired in a later
-- module; created now so the relationship exists.
CREATE TABLE daily_sales_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_date      TEXT NOT NULL UNIQUE,
    off_entry_id    INTEGER REFERENCES daily_sales_entry (id) ON DELETE SET NULL,
    road_entry_id   INTEGER REFERENCES daily_sales_entry (id) ON DELETE SET NULL,
    off_verified    INTEGER NOT NULL DEFAULT 0,
    road_verified   INTEGER NOT NULL DEFAULT 0,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
