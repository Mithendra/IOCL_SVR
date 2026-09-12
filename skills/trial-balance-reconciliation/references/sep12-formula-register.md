# Daily Trial Balance — formula register (source: SEP12 tab)

**Generated, not transcribed.** Re-run
`python skills/trial-balance-reconciliation/scripts/extract_formulas.py SEP12`
against `docs/01-BRD-Requirement-Gathering/ocr-samples/Trail_balance_12-SEP-2026.xlsx`
and diff the output to see exactly what the station changed. **322 formulas** in
that tab.

The client asked on 2026-09-12 whether these had ever been recorded, because
re-deriving them by hand is painful and has already been done more than once.
For Daily Sales Entry they had been (`skills/daily-sales-entry/references/formula-register.md`).
For Daily Trial Balance they had not — only SDD §9 and the 2026-09-06 audit,
neither of which is a per-cell record. This closes that gap, and it never has to
be done by hand again.

## Section 1 — IOCL Stock Readings

| Cell | Formula | SEP12 value | Built? |
|---|---|---|---|
| `D3` | `=B3-C3` — IOCL Last − IOCL Current | 577 | ✅ `diff` |
| `E3` | `=D15` — Actual Consump, from §2 combined | 591.87 | ✅ pulled |
| `F3` | `=E3-D3` — Consump Diff | 14.87 | ✅ `computer_pump_diff` |
| `G3` | `=E3-5.5` — Daily Testing | 586.37 | ✅ migration 0019 |
| **`H3`** | **`=G3*2.61`** — Margin HS = Daily Testing × 2.61 | 1,530.4257 | ✅ 0022 |
| **`H4`** | **`=G4*4.14`** — Margin MS = Daily Testing × 4.14 | 2,238.7878 | ✅ 0022 |
| `I4` | `=H3+H4` — Margin Total | 3,769.2135 | ✅ |
| `J4` | `=F26` — 2T Sales = Oil Sale(s) total | 416 | ✅ pulled |
| `K4` | `=I4+J4` — Total Sale Amt | 4,185.2135 | ✅ |
| **`L3`** | **`=F3*C67`** — IOCL Adv HS = Consump Diff × **Buy Rate HS** | 1,527.8925 | ✅ 0022 |
| **`L4`** | **`=F4*C68`** — IOCL Adv MS = Consump Diff × **Buy Rate MS** | 598.4612 | ✅ 0022 |
| `M4` | `=L3+L4` — IOCL Profit | 2,126.3537 | ✅ |

**2.61 / 4.14 are the per-litre margin (commission) rates**, HS and MS. They
appear again in the Section 9 ledger (`V109 =D109*4.14`, `W109 =E109*2.61`),
which is what confirms they are rates and not one day's constants.

## Section 2 — Day Sales Report

| Cell | Formula | Built? |
|---|---|---|
| `D7` | `=B7-C7` per pump/fuel consumption | ✅ from Daily Sales Entry |
| `F7` | `=(D7*E7)` per-pump amount | ✅ |
| `F9` / `F13` | `=SUM(...)` per-pump subtotal | ✅ |
| `B15` `C15` `D15` | `=D7` / `=D11` / `=B15+C15` — combined by fuel | ✅ |
| `F17` | `=SUM(F15:F16)` Total Sale | ✅ |
| `E19` | `=D19-B19` oil Closing = Opening − Sold | ✅ |
| `F19` | `=SUM(B19*C19)` oil amount = Sold × Rate | ✅ |
| `F26` | `=F19+…+F25` Oil Sale(s) total | ✅ |
| `E27` | `=F17+F26` Daily Sales Total Amt | ✅ |

## Section 3 — Daily Cash & Bank Balances

| Cell | Formula | Built? |
|---|---|---|
| `B34` | `=SUM(B29:B33)` → 3.6 Total | ✅ |
| `D35` | `=B34` → 3.7 | ✅ |
| `D41` | `=SUM(D35:D40)` → 3.13 Total Amt | ✅ |
| `D47` | `=SUM(D41:D46)` → 3.15 Total Cash/Book | ✅ |

## Section 4 — Cash/Book Value Reconciliation

| Cell | Formula | Built? |
|---|---|---|
| `D49` | `='SEP11'!D51` — yesterday, from the previous tab | ✅ ADR-2 carry-forward |
| `D51` | `=D49+D50` → 4.3 Total − Projected | ✅ |
| `D52` | `=D47` → 4.4 Reported = 3.15 | ✅ |
| `D53` | `=D52-D51` → 4.5 Difference | ✅ |
| `F54` / `F56` | `=D53` / `=F54-F55` — Difference less Yes Bank Return | ✅ |

## Section 5 / 6 — Stock Value, Trial Balance Actual Reported

| Cell | Formula | Built? |
|---|---|---|
| `B67` | `=C3` — Stock Ltrs = IOCL Current, verbatim | ✅ |
| `D67` | `=B67*C67` — Ltrs × Buy Rate | ✅ |
| `D69` | `=D67+D68` — Total Stock Value | ✅ |
| `D72` `D73` `D74` | `=D52` / `=D69` / `=D72+D73` — 6.1, 6.2, 6.3 Net Worth | ✅ |

## Section 7 — Trial Balance Projected

| Cell | Formula | Built? |
|---|---|---|
| `D76` | `='SEP11'!D79` — yesterday's actual reported TB | ✅ carry-forward |
| `D77` | `=K4` — Today's Profit Including 2T Sales = §1 Total Sale Amt | ✅ 0022 |
| `D78` | `=D76+D77` → 7.3 Projected | ✅ |
| `D79` | `=D74-D78` → 7.4 Difference | ✅ |
| `D80` | `=D78+D79` → 7.5 (identically 6.3) | ✅ |

## Section 8 — Daily Management Reporting

| Cell | Formula | Built? |
|---|---|---|
| `D82`–`D86` | `=D49` / `=D50` / `=D82+D83` / `=D52` / `=D85-D84` | ✅ |
| `D95` | `=D86+D88` — Cash Value Difference | ✅ |
| `D96`–`D101` | the net-worth summary, all references to §6/§7 | ✅ |
| **`D102`** | **`=D98-300-1666.66-666.66-666.66`** — Actual Profit after daily expenses; the four constants total **3,299.98**, which is the "Rs3300" in the label | ✅ 0022 |

## Section 9 — Daily Mgr Calculation (running ledger)

| Cell | Formula |
|---|---|
| `D109` / `E109` | `=B109-10` / `=C109-10` — deduct testing, **10 here, not 5.5** |
| `F109` / `G109` | `=D109*117.7` / `=E109*105.36` — at Sell Rate |
| `H109` | `=F109+G109` Total Sales Rs |
| `K109` | `=H109-I109+J109` Total Sale |
| `S109` | `=L109+…+R109` Total Cash After All |
| `V109` / `W109` | `=D109*4.14` / `=E109*2.61` — MS/HS Comm, the same margin rates |
| `X109` / `Y109` | `=V109+W109` / `=X109` — Total Comm, Day Profit |

**Open, flagged not guessed:** the ledger deducts **10** per fuel while Section 1
deducts **5.5** on the same day. Section 1 is the one the app computes and the one
that reconciles; the ledger is a hand-kept history. Worth asking the client which
is current before the ledger is ever computed rather than typed.
