-- "20/40 Engine Total in 05. Lts" -> "20/40 Engine Total in 1/2 Lts" (client,
-- 2026-09-29): "05." was meant to read as half a litre and was ambiguous on
-- the printed form; "1/2 Lts" says it plainly.
--
-- Same shape as every earlier oil-item relabel (2026-09-12): old label kept
-- in oil_item_alias so a day already saved under it still resolves to oil7,
-- inventory_item's display name updated to match, and rate_master's own
-- item_label brought into step on every dated row - it is what to call the
-- item, not a rate that changed on any of those dates, so there is no new
-- historical fact to add a row for (the same fix just applied in code to
-- api/oil_items.py's own PATCH endpoint, which was missing it entirely -
-- a rename through the app would otherwise have left this table stale and
-- silently broken the rate prefill for a row that looked perfectly normal).
INSERT OR IGNORE INTO oil_item_alias (label, item_key)
    VALUES ('20/40 Engine Total in 05. Lts', 'oil7');

UPDATE oil_item SET label = '20/40 Engine Total in 1/2 Lts', last_updated_by = 'migration-0054',
    last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE item_key = 'oil7';

UPDATE inventory_item SET item_label = '20/40 Engine Total in 1/2 Lts', last_updated_by = 'migration-0054',
    last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE item_key = 'oil7';

UPDATE rate_master SET item_label = '20/40 Engine Total in 1/2 Lts'
    WHERE item_key = 'oil7';
