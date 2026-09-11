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

## Recommendation

Run real-data UAT on **manual entry + Excel import + typed-PDF upload** (all
reliable). The OCR-of-handwriting path stays wired and bundled (costs nothing at
runtime) for the day a cloud/HTR option is chosen.

Black/blue ink and document scans (now the station standard) remove the
image-quality variable but **do not** make Tesseract read the handwriting —
tested directly (see the 2026-09-10 follow-up). The realistic paths to actual
capture are cloud handwriting OCR (option 3, breaks offline) or a trained model
(option 5). Neither is worth doing before UAT has run and the client has decided
whether OCR is a must-have. Do **not** rely on the current OCR output for real
figures.
