-- 0013_totp_challenge.sql - short-lived login challenge for two-factor auth
-- (SDD 4.x / 13.1). When a user with 2FA active passes the password step,
-- /auth/login issues one of these instead of a session; the 6-digit TOTP code
-- is then exchanged for a real session at /auth/login/totp. Single-use,
-- time-limited (SVR_TOTP_CHALLENGE_TTL_MINUTES, default 5).
--
-- users.totp_enabled / users.totp_secret already exist (0001_init.sql).
-- totp_secret is stored Fernet-encrypted (core/crypto), same as the employee
-- bank fields, and is never returned by any endpoint.

CREATE TABLE totp_challenge (
    challenge   TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_totp_challenge_user ON totp_challenge (user_id);
