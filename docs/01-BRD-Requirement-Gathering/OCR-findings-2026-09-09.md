# OCR (Scan / Upload) — findings on real station scans, 2026-09-09

## What was tested

The bundled Tesseract 5.3.3 (SDD ADR-6) was run against two real filled
**Daily Sales Report** pages the station provided:

| File (in `ocr-samples/`) | Source | Ink |
|---|---|---|
| `SVR-daily-sales-2026-09-08-road-scan.pdf` | document-scanner app | dark blue/black ballpoint |
| `SVR-daily-sales-2026-09-07-road-photo.pdf` | phone photo, "compressed" | **pink** ballpoint |

Pipeline: PDF → 300 DPI greyscale raster (PyMuPDF) → Tesseract (`--psm 6`,
`tessedit_create_tsv=1`) → word boxes → anchor-label field mapping
(`svr_backend/ocr/layout.py`) → plausibility filter → Daily Sales Entry draft.

## Result

**Printed template text: reads well.** "SVR Indian Oil Service Station – Daily
Sales Report", "Gas Sale(s)", "Current Reading", "Diesel (HS-Nz1)",
"Petrol (MS-Nz-2)", "Credit Cards Swiping(s)", "Summary – Cash Hand Off" etc. all
come through — enough to locate every section and row.

**Handwritten numbers: not usable.** Ground truth vs OCR for the six gas-row
fields on the *better* of the two samples (the scan):

| Field | On paper | Tesseract read |
|---|---|---|
| HS Current Reading | `1487517.430` | *(rejected — implausible)* |
| HS Last Shift Reading | `1486225.010` | `486225` (dropped leading `1` and `.010`) |
| HS Rate | `105.36` | *(rejected)* |
| MS Current Reading | `660581.140` | `-4034300` |
| MS Last Shift Reading | `660268.480` | `662698` |
| MS Rate | `117.70` | *(rejected)* |

**0 of 6 correct.** The phone photo (pink ink) yielded **0 fields** — the
plausibility filter rejected everything, correctly.

### Follow-up attempt, 2026-09-10 — preprocessing + per-cell OCR

After the station confirmed sheets will always be **black or blue pen** (the pink
photo was a one-off), the *black-pen DocScanner* sample was re-run with a much
harder pipeline: 400 DPI, per-field **cell crops** from the anchor grid, 4×
upscale, autocontrast, binarise, median-denoise, and Tesseract with a
digits-only whitelist swept across `--psm 7 / 8 / 13 / 6`.

Still **0 of 6 exact.** The reads got *closer in places* — `1486225.010` came
back as `6225.010…` (correct tail, lost `1486` and bled into the next column),
`105.36` as `336` — but nothing clean or trustworthy. Isolating one number in a
denoised crop is the strongest thing Tesseract can be given, and it still can't
read this handwriting.

## Why

Tesseract is an OCR engine for **printed** text. It has no handwriting model, and
`eng.traineddata` is print-only. Joined-stroke handwritten digits are outside
what its LSTM can do regardless of ink colour, scan quality, or preprocessing —
confirmed across three approaches (full page, plausibility-filtered, and
per-cell + denoise), all 0/6 on a clean black-pen document scan. The bundled
engine, rasteriser, and field mapping all work; the input is just not something
Tesseract can read.

## What ships anyway

`POST /daily-sales-entry/ocr` is wired as **draft-assist only**:

- accepts a PDF or image, returns a Daily Sales Entry draft + per-field
  confidence + the raw page text + a mandatory `OCR DRAFT …` warning;
- **never saves** — the operator reviews on the normal screen and Saves through
  the RBAC'd path, which recomputes every total (SDD ADR-5);
- the Scan / Upload button shows the draft in **red** with "Handwriting is NOT
  read reliably — check EVERY value before Save".

In practice, with ~0 fields correct, this is close to no help on the current
forms. It is left in because (a) the plumbing is real and correct, and (b) it
improves immediately if the inputs improve (see below).

## Options for actually capturing the numbers

1. **Manual entry + attach the scan** *(recommended now)* — the operator types
   from the paper (or from the physically present sheet), and the PDF/photo is
   kept with the record as the audit artifact. No accuracy risk. *(The "attach a
   file to the entry" piece is not built yet — small addition if wanted.)*
2. **Better source images** — a flatbed/ADF scan, **black** ink, 300 DPI,
   de-skewed, high contrast. Won't make Tesseract read cursive, but clean
   separated digits in dark ink do lift its digit accuracy materially. Worth a
   re-test if the station standardises how sheets are scanned.
3. **Cloud handwriting OCR** — Google Document AI / Azure AI Document
   Intelligence / AWS Textract read handwritten forms well. **Breaks the
   offline/on-prem rule** and sends the dealership's financial records to a third
   party; also a per-page cost. Only if the client accepts both.
4. **Digit-cell OCR with heavy pre-processing** — detect the table grid, crop each
   value cell, binarise/denoise, OCR with a digit whitelist. Larger effort, still
   capped by the handwriting problem; modest upside.
5. **Train / fine-tune a handwriting model** (Tesseract LSTM or a small CNN on
   the station's own sheets). Real project; hard to justify for one outlet.

### Update, 2026-09-10 — typed / machine-generated PDFs work

A handwritten sheet was transcribed into the SVR template as a **typed B&W PDF**
(`ocr-samples/SVR-daily-sales-2026-09-09-typed-bw.pdf`). Tesseract still read it
poorly — **but that PDF has a real text layer**, so OCR is the wrong path for it
entirely. The pipeline now checks for a text layer first (`pymupdf.get_text`) and
reads it verbatim, no OCR:

- **8 / 8 mapped fields exact** (HS/MS current, last, rate; Phone Pay Settled;
  Night Cash) — recomputes to the paper figures (`hs.cons 310.68`,
  `hs.amount 32733.24`, `ms.cons 583.55`, …).
- `engine` reports `PDF text layer`; the UI shows a calm "check each value" note,
  not the handwriting warning.

**So there is a working Scan/Upload path** for anyone who fills the form
digitally or transcribes it into the typed template and saves a PDF — the app
extracts it and the operator just reviews. Only a **direct scan of handwriting**
remains unreadable.

### Update, 2026-09-10 — the same idea now works for Excel too

Client asked the mirror-image question: rather than a typed PDF, can a handwritten
form be typed up into an **Excel sheet** (e.g. via an AI chat tool) and imported
directly? `POST /import-excel` previously only understood our own keyed
export/template layout - a natural, paper-shaped workbook (labels beside values,
no hidden field-key column) came back with "No SVR field keys found" and an empty
form. `excel/daily_sales_entry.py` now falls back to a **paper-layout parser**
(`_parse_paper_layout`) that matches the physical form's own labels by exact cell
text (not OCR) when no keys are found - same review-before-Save discipline (ADR-5),
no OCR engine involved. So there are now **two** working manual-conversion
workflows, covering the two natural output formats an AI transcription tool
produces:

- **typed PDF → Scan/Upload** (text-layer read, above)
- **typed Excel → Import from Excel** (paper-layout fallback)

Both are entirely manual and external to the app - a person converts the
photographed form using whatever tool they choose, outside the SVR application,
then imports the result through an existing button. The app has no direct
integration with (and makes no runtime call to) any AI/cloud service either way.

### Update, 2026-09-10 — validated against the client's real file

The client's actual `.xlsx` (it arrived corrupted the first time it was sent)
is now in `ocr-samples/SVR_Daily_Sales_FILLED_SEP10_BLACK_WHITE.xlsx`, alongside
a reference blank form, `ocr-samples/SVR_EMPTY_FORM_FINAL.pdf` (confirms Print /
Print Blank should cover Sections 1-7 + Verified by only - already how it's
built). Reading the real file:

- **Gas Sale(s), Expenses, Phone Pay Settled, and Night Cash all read exactly
  right** and recompute to the same figures printed on the paper form
  (`hs.cons 310.68` / `hs.amount 32733.24`, `ms.cons 583.55` / `ms.amount
  68683.83`, …) - covered by `test_real_client_workbook_reads_the_gas_and_
  expense_figures` in `test_excel_paper_layout_import.py`.
- **Oil Sale(s) needs a careful look**: this workbook's "Quantity" column holds
  different numbers than the previously-supplied typed PDF of the same day's
  data for the 3 rows where Quantity should be blank (e.g. row 1 has `30` under
  Quantity here, where the PDF has Quantity blank and `30` under Rate instead).
  This reads as a genuine inconsistency between the two client-supplied
  transcriptions of the same paper form, not a parser defect - the parser reads
  exactly what's under each column header, which is all it can do. This is
  exactly the case SDD ADR-5's mandatory review-before-Save exists for; flagged
  here so a human specifically re-checks the Oil Sale(s) quantities against the
  original paper form before Save when using this workflow.

### Update, 2026-09-11 — six more real files: a repair-gap, a two-sheet
### workbook, a "-" convention, and a mislabeled earlier sample

Client delivered six real Daily Sales Report files spanning 2026-09-09/10, the
exact days the Road pump (12BC4523V-RD) was out for repair and then came back.
All six now in `ocr-samples/SVR_Daily_Sales_{09,10}Sep2026_*.{pdf,xlsx}`.

- **The gas readings (Current/Last Shift/Cons) read correctly from every one
  of the three typed PDFs**, via the text-layer path - no OCR needed, same as
  the earlier finding. `test_ocr_text_layer.py`-style coverage would apply the
  same way; verified directly against all three files.
- **Phone Pay Settled / Not Settled came back blank from the PDF text-layer
  path on the busier Office-pump form** (one with real Credit Cards Swiping
  rows filled in), even though the value is present and printed - the field's
  row-matching by anchor text didn't line up on this particular layout. The
  **Excel version of the same file reads it correctly** (paper-layout parser,
  exact cell match, not position-dependent). **Practical recommendation: for a
  typed/AI-transcribed report, prefer Import-from-Excel over Scan/Upload when
  the two disagree** - it gets every field, not just the gas readings, and
  isn't sensitive to how much content pushes the Summary section down the
  page. Not fixed in the OCR layout code this round (real financial fields
  read fine either way for the pumps validated so far); worth a proper anchor-
  matching fix if Scan/Upload keeps being the client's preferred path.
- **One real workbook has two sheets** - Road and Office data for the same day
  in one file (`SVR_Daily_Sales_10Sep2026_12BC4523V-RD.xlsx`). Fixed: import
  now reads the sheet matching whichever Pump Serial Number is selected on the
  form, not just whatever sheet is "active" (previously would have silently
  dropped one pump's data with no warning at all). See the code changes for
  the full description.
- **The paper form's own "-" convention** (used everywhere for "nothing to
  report" - blank oil quantities, blank credit-card rows, blank summary lines)
  was being read as the literal two-character string `"-"` instead of blank,
  polluting the parsed payload with dash values that didn't affect totals but
  would have shown as filled-in "-" boxes on the review screen instead of
  genuinely blank ones. Fixed in `calc.amounts.is_blank` and the Excel
  parser's own `_num_or_str`, both used pervasively - a lone `"-"` is now
  blank everywhere in this system, the same way an empty cell is.
- **A repair-gap carry-forward, validated with real numbers, not synthetic
  ones**: the Office pump's Last Shift Reading auto-carries correctly across
  three real consecutive days (09-08 → 09-09 → 09-10), reproducing the exact
  consumption printed on each real paper form. The Road pump's first entry
  after its repair gap (09-10) has nothing in the system to carry from - no
  digital record of the repair day exists, nor of anything before it - so the
  Last Shift Reading has to be keyed in by hand from the station's own paper
  log; the 2026-09-11 fix that allows a manual override when there's nothing
  to carry handles exactly this case, and it reproduces the real paper's
  consumption figures exactly too. See `test_real_data_2026_09_11.py`.
- **Found while cross-checking, not part of this delivery**: an earlier
  sample already in this repo,
  `ocr-samples/SVR-daily-sales-2026-09-08-road-scan.pdf`, is **mislabeled** -
  its handwritten "Road Side" annotation and filename both say Road, but its
  actual readings (~1,487,xxx) are the *Office* pump's - they match this
  delivery's Office-pump Last Shift Reading for 2026-09-09 exactly
  (1487517.430). Left as-is (it's still useful OCR-accuracy test data, just
  not Road-pump data); flagged here so it's not mistaken for a real Road-side
  reading in the future.

### Update, 2026-09-11 (same day) — the actual go-forward workflow, confirmed

Two more real files arrived the same day: `SVR_Daily_Sales_09Sep2026_
12BC4523V-RD_.pdf`/`.xlsx` - the Road pump's own report for the repair day
itself. This settles the "what happens on a repair day" question more
precisely than the earlier entry above: the client's real workflow is **the
repaired pump still submits a report that day**, with Current Reading ==
Last Shift Reading (0 consumption, 0 amount, everything else blank) - not
skipped entirely. The very next day (09-10) then carries forward from it
automatically, with no gap at all.

Validated end to end, with real numbers, in `test_real_data_2026_09_11.py`
(`test_road_pump_zero_activity_repair_day_then_seamless_carry_forward`) and
against the PDF/Excel files directly (`test_ocr_text_layer.py`'s parametrized
2026-09-11 cases, `test_excel_paper_layout_import.py`'s
`test_zero_activity_repair_day_reads_current_equal_to_last`). All four
2026-09-09/10 typed PDFs read correctly from the text layer (gas readings
exact in every case); all four .xlsx read correctly via the paper-layout
parser, including Phone Pay Settled/Not Settled where the PDF path missed it
on the busier Office-pump forms (per the entry above - unchanged finding,
confirmed again on the Sep-9 Office file too).

## Recommendation

Run real-data UAT on **manual entry + Excel import (keyed template or a natural
paper-shaped workbook) + typed-PDF upload** (all reliable, no OCR engine
required). The OCR-of-handwriting path stays wired and bundled (costs nothing at
runtime) for the day a cloud/HTR option is chosen.

Black/blue ink and document scans (now the station standard) remove the
image-quality variable but **do not** make Tesseract read the handwriting —
tested directly (see the 2026-09-10 follow-up). The realistic paths to actual
capture are cloud handwriting OCR (option 3, breaks offline) or a trained model
(option 5). Neither is worth doing before UAT has run and the client has decided
whether OCR is a must-have. Do **not** rely on the current OCR output for real
figures.
