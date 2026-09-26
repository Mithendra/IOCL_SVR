-- The station's own name, address and phone, for anything it hands to a
-- customer. Client gave these 2026-09-25 for the Payment Receipt:
--
--   SVR IndianOil Service Station
--   14-1-108/1, G.B.C Road, Guntur Dist, Ponnur, Andhra Pradesh - 522124
--   Tel +91 90329 59091
--
-- (Spaced, deliberately. Written as one unbroken string it is a twelve-digit
--  run, and test_no_bank_identifiers.py flags that as an account number -
--  correctly, it cannot tell the two apart from digits alone. Widening that
--  guard to let a phone number through would blunt the check that keeps real
--  bank identifiers out of a public repo, so the number is spaced instead.)
--
-- A table rather than constants in the renderer, because a receipt is a document
-- that leaves the station and the details on it have to be correctable by the
-- Owner without a rebuild - the same reasoning as ADR-3, which cannot be used
-- directly here because system_parameter.value is REAL and these are text.
--
-- Free-form key/value on purpose: a GSTIN or a licence number will be wanted on
-- the receipt sooner or later, and that should not need another migration.
CREATE TABLE station_profile (
    key              TEXT PRIMARY KEY,
    value            TEXT NOT NULL,
    last_updated_by  TEXT,
    last_updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO station_profile (key, value, last_updated_by) VALUES
    ('name',     'SVR IndianOil Service Station',                             'client-2026-09-25'),
    ('address1', '14-1-108/1, G.B.C Road',                                    'client-2026-09-25'),
    ('address2', 'Guntur Dist, Ponnur, Andhra Pradesh - 522124',              'client-2026-09-25'),
    ('phone',    '+91 90329 59091',                                           'client-2026-09-25');
