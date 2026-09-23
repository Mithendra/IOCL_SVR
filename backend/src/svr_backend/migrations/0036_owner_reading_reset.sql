-- Owner-only reset of the carried Last Shift Reading, behind its own passphrase.
--
-- Client, 2026-09-23: "Define a small owner form where you can reset the last
-- reading for both pumps. To open that form you need to have a secret password."
--
-- WHY A SECOND SECRET AT ALL. Being logged in as Owner already gates plenty.
-- This one is different: a meter reading is the base every later day is measured
-- from, so a wrong reset does not spoil one form - it silently re-bases the
-- station's consumption from that day forward. The passphrase is deliberate
-- friction on an unsigned-in-the-moment mistake (an Owner's session left open on
-- the counter), not a claim of cryptographic defence.

-- The passphrase itself is NEVER stored. Only an Argon2 hash of it, in a table
-- with no listing endpoint, set by the Owner on first use. Nothing ships a
-- default: a default passphrase in a public repository is not a passphrase.
CREATE TABLE owner_secret (
    id               INTEGER PRIMARY KEY CHECK (id = 1),   -- exactly one row
    passphrase_hash  TEXT NOT NULL,
    last_updated_by  TEXT NOT NULL,
    last_updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A reset does not edit history. It records "as of this date, this pump's meter
-- reads X", and the carry-forward prefers whichever is later - this baseline or
-- the last saved entry. Editing the old entry instead would change a day the
-- station has already signed off, and rewriting a closed day to fix today is how
-- audit trails stop meaning anything.
CREATE TABLE reading_baseline (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pump_serial     TEXT NOT NULL,
    effective_date  TEXT NOT NULL,          -- the reading is true as of this date
    hs_last         REAL,
    ms_last         REAL,
    reason          TEXT NOT NULL,          -- required: a reset with no reason is a mystery later
    last_updated_by TEXT NOT NULL,
    last_updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_reading_baseline_pump_date
    ON reading_baseline (pump_serial, effective_date DESC, id DESC);
