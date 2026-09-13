-- Oil Sale(s) items become DATA, not code (client, 2026-09-13: "people should be
-- able to add it, or people should be able to remove it").
--
-- Until now the seven rows lived in a Python tuple (OIL_ITEMS in
-- calc/daily_sales_entry.py). Adding an eighth meant a code change, a migration
-- and a release - which is why the 2026-09-12 revision from five rows to seven
-- had to be done by hand across six modules. The station sells what it sells; the
-- list belongs to the Owner, not to the build.
--
-- item_key still identifies a PRODUCT, not a row position. That rule is what
-- preserved oil1/oil4/oil5 through the 2026-09-12 relabel, keeping their Rate
-- Master history and tracked stock, and it does not change here: the table keys
-- on item_key and the display order is a separate column.
--
-- REMOVING an item is a deactivation, never a delete. Days already recorded name
-- the item in their own saved rows; deleting it would leave those rows pointing at
-- nothing and silently change historical totals. An inactive item drops off the
-- entry form but still resolves when an old record is read back.

CREATE TABLE oil_item (
    item_key        TEXT PRIMARY KEY,   -- 'oil1'.. stable for the product's life
    label           TEXT NOT NULL UNIQUE,
    unit            TEXT NOT NULL DEFAULT 'pcs',
    sort_order      INTEGER NOT NULL,   -- position on the form; gaps are fine
    active          INTEGER NOT NULL DEFAULT 1,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_oil_item_order ON oil_item (active, sort_order);

-- Every label this station has ever used, mapped to the product it names. A saved
-- row carries its own label, so this is what lets a 2026-09-09 record still
-- resolve after the row was relabelled and the order changed underneath it. Was
-- LEGACY_OIL_LABELS in the calc module; it has to live here now because a rename
-- through the UI adds to it.
CREATE TABLE oil_item_alias (
    label    TEXT PRIMARY KEY,
    item_key TEXT NOT NULL REFERENCES oil_item (item_key)
);

-- The seven as of 2026-09-12, in the client's own display order. sort_order is
-- spaced by 10 so a new item can be slotted between two existing ones without
-- renumbering the rest.
INSERT INTO oil_item (item_key, label, unit, sort_order, last_updated_by) VALUES
    ('oil1', '2T/1.50 ML Total#',             'pcs', 10, 'migration-0023'),
    ('oil2', '2T/2.40 ML Total#',             'pcs', 20, 'migration-0023'),
    ('oil3', 'Acid Water Total 1 Lts',        'ltr', 30, 'migration-0023'),
    ('oil6', 'Battery Water Total 1 Lts',     'ltr', 40, 'migration-0023'),
    ('oil4', 'Battery Water Total 5 Lts',     'pcs', 50, 'migration-0023'),
    ('oil7', '20/40 Engine Total in 05. Lts', 'ltr', 60, 'migration-0023'),
    ('oil5', '20/40 Engine Total in 1 Lts',   'ltr', 70, 'migration-0023');

-- Current labels resolve to themselves...
INSERT INTO oil_item_alias (label, item_key)
SELECT label, item_key FROM oil_item;

-- ...and the three labels retired on 2026-09-12 still resolve to their product,
-- so records written before that date read back correctly (was LEGACY_OIL_LABELS).
INSERT INTO oil_item_alias (label, item_key) VALUES
    ('2T/1.20 ML Total#',        'oil1'),
    ('Acid Water Total 5 Lts',   'oil4'),
    ('20/40 Engine Total in Lts','oil5');
