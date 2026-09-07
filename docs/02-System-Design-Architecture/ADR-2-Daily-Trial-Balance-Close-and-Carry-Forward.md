# ADR-2 — Daily Trial Balance: Close & Sign-Off Carry-Forward

**Status:** CONFIRMED with client 2026-09-06 — including the RBAC maker–checker shape (point 4 below) and the live-projected-balance question (Consequences). **IMPLEMENTED 2026-09-06** — Decision steps 1–4 are built and covered by `backend/tests/test_daily_trial_balance_api.py` (full suite, including the pre-existing tests, verified green: 94 passed). Point 5 (gap-day handling for a real multi-day closure) remains open — see "Current code state" below. Extends ADR-1 (§8.5); does not conflict with §7.7.
**Relates to:** ADR-1 (Sections 2/4/5/8/9/10/11 confirmed Manual Blob 2026-09-06 — still a separate decision from this one), SDD §7.7 (23:59 IST scheduler carry-forward for Last Shift Reading).

## Context

ADR-1 (§8.5) left open whether Daily Trial Balance's duplicate-entry sections should become read-only rollups from other modules. A related but distinct question was raised while auditing the client's legacy Excel workbook (322 daily tabs, Oct 17 2025 – Sep 6 2026) as a reference for how the Trial Balance module should behave: **how does each day's opening cash/book value and opening stock value get carried forward from the previous day's closing values, and what should trigger that in the application?**

The legacy workbook implements this by hand: each day's tab is copied from the previous day's, with a literal formula reference (e.g. `='SEP05'!D51`) typed into the new tab pointing at yesterday's closing figures. A full recompute-and-compare audit of that workbook found:

- **All 23,025 formula cells across all 322 daily tabs recompute correctly against their cached values** — the day-to-day arithmetic itself has never been wrong.
- **Two carry-forward failures, both caused by the hand-typed reference itself, not the math:**
  1. `SEP02!D96` ("Yesterday's Actual Reported Trial Balance") was wired to `='AUG31'!D78`, skipping Sep 1 entirely — produced a misleading ~₹22,538 variance that day that was really just a broken link.
  2. A secondary "Computer Stock Value Margin Yesterday to Today Sale" reconciliation panel had its "Yesterday Stock Value" cell hardcoded to `='JUN4'!D83` across ~56 consecutive tabs (Jun 6 – Aug 1), frozen instead of updating daily — a copy-pasted tab where the link was never updated. Did not corrupt the main reported Trial Balance, but made that panel's check non-functional for two months.

Both failures share one root cause: **carry-forward implemented as a human-typed literal reference, with no system-level check that the reference points at the correct, complete prior day.**

## Why this is not the same problem §7.7 solves

§7.7's 23:59 IST scheduler job is correct for the Last Shift Reading because a meter reading is a **fact about the physical world at a point in time** — it doesn't require anyone's judgment, so a blind clock-triggered job is the right tool, and its documented gap-day/catch-up handling is sufficient.

Trial Balance's opening cash/book and stock value are different: they depend on that day's cash count, bank/UPI reconciliation, and expense entries all being **complete and correct** before they can be trusted as tomorrow's starting point. A blind scheduler firing at a fixed hour cannot know whether that's true yet — it would either lock an incomplete day or force a rigid entry deadline on the till. This calls for a trigger tied to human confirmation, not the clock.

## Decision

Daily Trial Balance's day-to-day carry-forward is triggered by a **"Close & Sign Off" action in the Daily Trial Balance entry form, performed by the Manager role**, not by a scheduled job. Concretely, on submit this single atomic action:

1. **Validates** the entry is complete and re-runs the variance/escalation check server-side (the existing ₹100 threshold rule from the legacy sheet's own notes). If breached, the Manager must enter a short reason before sign-off is allowed — turning a comment nobody reliably reads into an enforced field.
2. **Locks** the record (`status = CLOSED`, with who/when signed off). No further silent edits; a later correction is a separate audited adjustment entry, never an in-place overwrite.
3. **Creates the next day's entry**, with opening cash/book and stock values populated from this record's own closing values via a system-generated link (e.g. `prev_day_id` foreign key) — never a human-typed sheet or date reference. This is what structurally prevents both failure modes found in the audit: there is no cell to mistype, and no template to copy forward with a stale reference baked in.
4. **Refuses to create the next day's entry if the current day isn't yet Closed** — this alone would have caught the Sep 1 skip directly, since Sep 2 could not have been created without Sep 1 first being signed off.

### Non-negotiable invariant: carry forward the Reported values, never the Projected ones

The legacy sheet keeps two parallel figures every day — an **Actual Reported** value (what the manager actually signed off, e.g. `D51`/`D79` in the old sheet's lettering) and a **Projected** value (what the numbers were expected to be, e.g. `D50`/`D77`). Only the **Reported** ones may ever feed the next day's opening balance. This matters enough to call out explicitly because both figures exist side by side in the schema and it is easy to wire the wrong one in: `trial_balance_7_1` (cash/book value) and the finalized Section 7 total in the current calc engine are the Reported figures — carry-forward must always read from these, post-finalize, never from a same-day Projected/draft computation. This is also exactly the class of mistake that caused the Sep 2 skip: a link pointing at the wrong figure/day rather than the correct one.

**Workflow (maker–checker, confirmed with client):** normally, one person enters and validates the day's data (the maker) and the Manager performs Close & Sign Off (the checker) — mirroring the legacy sheet's own "Prepared by / Verified by" fields. When the maker is unavailable (e.g. off that day), the same Manager may perform both steps — this is an allowed fallback, not an error path, and the system should not block it. Single-manager sign-off is sufficient either way; no dual-approval requirement at this stage.

**Secondary, non-authoritative automation:** a lightweight scheduled check (e.g. daily ~10:30 IST, matching the business's own shift-start convention) may send a reminder/escalation if the previous day still isn't Closed. It never modifies the ledger itself — decision authority stays entirely with the Manager; automation only prompts a human.

## Current code state (as of 2026-09-06) — IMPLEMENTED

All four items below shipped 2026-09-06 in `backend/src/svr_backend/api/daily_trial_balance.py` (migration `0012_daily_trial_balance_carry_forward.sql`), verified against the full backend test suite (94 passed, 0 failed) run locally before this file was pushed back to the repo:

1. **Auto-carry-forward — done.** `finalize_trial_balance` now creates the next calendar day's draft inside the same transaction, seeding `s1_hs_yesterday`/`s1_ms_yesterday` from this day's own `s1_hs_current`/`s1_ms_current`, and `s54_cash_book_value` from this day's own value — via `prev_trial_balance_id`, a real foreign key, never a human-typed date/cell reference. A maker-supplied value for that date still overrides the seed. Covered by `test_finalize_creates_and_seeds_the_next_day`.
2. **Gating on the previous day — done.** `upsert_trial_balance` refuses to create a brand-new `shift_date` while any earlier date is still open (not finalized) — `test_cannot_skip_ahead_while_an_earlier_date_is_open` reproduces the exact SEP02 shape (an attempt to start a far date while an earlier one sits as an open draft) and gets a 409 naming the blocking date.
3. **Variance/escalation check — done.** `POST .../finalize` now accepts an optional `{projected_total, reason}` body. When `projected_total` is supplied, the difference against the computed Reported total (`result_json.section7.7_3_total`) is checked against the existing `trial_balance_alert_threshold` system_parameter (seeded ±₹100); a breach without a `reason` is rejected (422). `variance_amount`/`variance_reason` are stored on the row and returned in the view. **Scope note:** when `projected_total` is omitted, the check is skipped rather than blocking sign-off — the Projected total isn't computed server-side yet (its inputs live in ADR-1's still-manual sections), so this is best-effort until that figure exists. Covered by `test_variance_escalation_requires_a_reason_over_threshold`, `test_variance_within_threshold_needs_no_reason`, `test_finalize_without_projected_total_skips_the_check`.
4. **RBAC — done.** `GET`/`PUT /{shift_date}` now allow `Sales, Manager, Owner` (the maker role, per the SDD's three-role model); `POST /{shift_date}/finalize` (Close & Sign Off) stays `Manager, Owner` only. The module docstring's old "Sales has no access at all" line is removed. The API does not enforce that the maker and finalizer differ on any given day — a Manager/Owner may still do both, the explicitly-allowed fallback. Covered by `test_maker_checker_rbac`.

**Point 5 — gap-day handling for a real multi-day closure — still open, by design.** Because finalize *eagerly* creates tomorrow's draft every time (point 1 above), a genuine multi-day closure (a festival holiday, say) leaves a chain of empty auto-created drafts that each still need Close & Sign Off before a far-out date can be started — `test_reopening_after_a_gap_still_needs_each_auto_created_day_closed` documents this honestly rather than papering over it. The one case gap-tolerance *does* cover today is a cold start on an arbitrary date when no row exists anywhere yet (`test_cold_start_on_an_arbitrary_date_has_no_gate_and_no_seed`) — there's nothing earlier to gate on. True multi-day skip-back (mirroring §7.7's precedent fully) needs its own follow-up decision: e.g. an explicit "no activity, close in bulk" action for the empty auto-created days in between, rather than requiring each to be individually signed off. Not designed or built here — flagging it rather than deciding it silently.

## Consequences

- Does not resolve ADR-1's remaining scope: Sections 2/4/5/8/9/10/11 are **CONFIRMED 2026-09-06 as Manual Blob** (a separate decision from this one) — this ADR only settles the *day-to-day carry-forward trigger* for the fields that are server-computed (Sections 1/6/7).
- **"Real-time" — resolved 2026-09-06, unchanged by this implementation.** The Projected Trial Balance figure recomputes live through the day, but from manual entries only. `upsert_trial_balance` already calls `compute()` and stores a fresh `result_json` on every `PUT`; once carry-forward populates yesterday's Reported value (implemented above), that existing per-save recompute is sufficient — no new streaming/live-update infrastructure was needed.
- **Follow-up decision needed:** point 5's multi-day gap handling, above.

## Verification note

This decision was informed by an actual audit of production-equivalent data (the client's own Sep 5/Sep 6 daily tabs, cross-checked against the full historical workbook), not a hypothetical — the specific failure modes it addresses are documented above with cell references so they can be re-verified against the source workbook if needed.
