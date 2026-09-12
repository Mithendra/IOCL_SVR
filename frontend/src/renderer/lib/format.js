// Display formatting. Values stay numeric everywhere in the payload and in the
// calculation engine - this module only controls how they are shown
// (client-required 2026-09-11: every figure on every screen reads to exactly
// two decimals, so 102727.0798 shows as 102727.08 and 8560 as 8560.00).
//
// Deliberately NOT applied to a field while someone is typing in it: the paper
// form's inline scratch-sum syntax ("527+588+100=1215") has to survive
// round-trip, and reformatting mid-edit would destroy it.

/** A number (or numeric string) as exactly two decimals. Blank stays blank. */
export function fmt2(v) {
  if (v === undefined || v === null || v === "") return "";
  const n = typeof v === "number" ? v : Number(String(v).trim());
  if (!Number.isFinite(n)) return String(v); // leave un-numeric text alone
  return n.toFixed(2);
}

/** Same, but renders blank/unparseable as "0.00" - for total cells that should
 *  always show a figure rather than an empty box. */
export function fmt2zero(v) {
  const out = fmt2(v);
  return out === "" ? "0.00" : out;
}
