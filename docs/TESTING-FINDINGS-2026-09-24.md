# Testing findings — 2026-09-24, manual data entry

Running list, written as the client tests. Each item records what they saw, what
I found in the code, and whether it is a defect or working as designed.

Nothing here is fixed unless it says so. Items are added in the order reported.

---

## 1. Inventory Master has no Save button — OPEN, confirmed

**Client:** *"updated inventory master and there is no Save Button which is
needed, or need a Delete and Update buttons."*

**Confirmed in the code.** The screen has exactly one button, `Add Restock`
([inventory-tracking/index.html:64](../frontend/src/renderer/screens/inventory-tracking/index.html#L64)).
Both editable figures save on a `change` event — that is, silently, when the
field loses focus:

```js
el.addEventListener("change", () => saveOnHand(el.dataset.key, el.value));   // :52
el.addEventListener("change", () => saveReorder(el.dataset.key, el.value));  // :47
```

So a number is written to the database the moment you tab out of the cell, with
no confirmation that it happened and no way to change your mind.

**Why this matters more than it looks.** On Hand is the opening stock every
later day is measured from — the same class of figure as the Last Shift Reading
that caused the SEP15 trouble. Saving it on blur means:

- the operator gets no confirmation, so they cannot tell a saved edit from a
  typo that was also saved;
- a mistyped digit is committed before it can be reviewed, and there is no
  undo;
- clicking away mid-edit (to check a figure on the sheet) commits whatever is
  in the box at that moment.

**What to build:** an explicit **Save** per row or for the screen, with the
usual status line confirming what was written; **Update** is the same action
under a clearer name. **Delete** needs a decision — see the question below.

**Open question for the client:** what should Delete remove?

- the *stock figure* (set On Hand back to zero / blank), or
- the *item itself* from the Inventory Master?

Retiring an item is not the same as zeroing it, and the app already retires oil
items rather than deleting them, precisely so a past day that sold one still
adds up. I have not guessed at this.

---

## 2. "+ New Oil Item" belongs on Inventory Master, not Daily Sales — OPEN, confirmed

**Client:** *"New Oil Item is not needed on the Daily Sales form, which should be
there in Inv Master only."*

**Confirmed.** The control lives on Daily Sales Entry
([daily-sales-entry/index.html:195-204](../frontend/src/renderer/screens/daily-sales-entry/index.html#L195))
— `+ New Oil Item`, with its name / rate / opening-stock box and a retire column
on each row. Inventory Tracking has **none** of it: zero matches for that button
there.

They are right about where it belongs. Adding or retiring a product is a
*catalogue* decision the Owner makes now and then; Daily Sales Entry is a form
someone fills in every shift. Putting the two together invites a new item being
created in the middle of keying a day, and the print CSS already has to hide the
whole block so it does not appear on the paper form — which is the tell that it
was never part of the form to begin with.

**What to do:** move the block to Inventory Tracking, with the same
Manager/Owner gate it has now, and drop it from Daily Sales Entry. The rows
themselves stay on Daily Sales Entry — only the add/retire controls move.

**Care needed:** retiring must keep working the way it does today. A day
recorded before an item was retired still shows that row, marked retired, rather
than dropping it — otherwise the screen recomputes an old day from the rows it
can see and shows a smaller Oil Total than the one actually stored. That
behaviour is deliberate and must survive the move.

---

## 3. Old Credit Given Date has no calendar — OPEN, confirmed

**Client:** *"6. Old/Pending Credit Received — column Old Credit Given Date
should have a calendar listed."*

Confirmed. The cell renders as a plain text box:

```js
'<td><input class="oc-given"></td>'   // screen.js:271
```

while Shift Date, the Query From/To range and the Owner reset date all use
`type="date"` and get the native picker. So it is an inconsistency inside one
screen, not a considered choice.

This is the same thing reported earlier as *"Date - No calendar here"*, so the
two are one item.

---

## 4. Print printed a blank form after data was entered — NEEDS A DECISION

**Client:** *"Print is not working as data entered"*, with the printed PDF
attached.

**What the PDF actually is.** It is the BLANK form, correctly produced: Last
Shift Reading 1,489,759.27 and 663,546.17, the oil Rates and Opening Stock, and
every other cell empty. That is exactly what `Print Blank DSR` is built to emit -
the carried reading plus the pre-printed figures, everything else left for a
pen. The layout itself is right; it matches the station's reference blank.

So nothing malfunctioned. Either the Blank button was pressed, or - and this is
the part worth changing - the Filled button was pressed and refused.

**The design decision behind it, which I think is wrong.** `Print Filled DSR`
deliberately prints what is SAVED for that pump and date, not what is on the
screen:

```
// Print what is SAVED for the day, not what happens to be on screen: a form
// that shows unsaved edits is a form that disagrees with the database.
```

My reasoning was that a printed form is a record, and a record that disagrees
with the database is worse than no record. The operator's expectation is the
opposite and more obvious: they have just keyed a day, they press Print, and
they expect to see what is in front of them.

Both views are defensible, so this is the client's call:

- **Print what is on screen.** Matches expectation. Risk: a form can be printed,
  signed and filed for a day that was never saved, and nothing in the app would
  know about it.
- **Keep printing only saved data, but say so properly.** The refusal message
  exists but is easy to miss - it lands in the status line. It could instead
  offer to save and then print, which gets the expected result without ever
  producing a form the database cannot account for.

My recommendation is the second: **Save & Print**, one button, so the printed
form and the record always agree. But it is their form and their process.

**Not changed.** The client asked for no changes while testing.

---

## 5. Verified By / Signature / Date — no calendar, and not stored at all
*(the client numbered this one 4 as well; it is listed after the print item.)*

**Client:** *"Verified By / Owner / Signature / Mithendra / Date — this column is
not listing the calendar."*

**Confirmed, and there is a second problem underneath it.**

```html
<div class="field"><label>Verified By</label><input id="verify-name" disabled /></div>
<div class="field"><label>Signature</label><input type="text" /></div>
<div class="field"><label>Date</label><input type="text" /></div>
```

1. **Date is `type="text"`**, so no picker - the same inconsistency as the Old
   Credit Given Date in item 3. Shift Date, the Query range and the Owner reset
   date all use `type="date"`.

2. **Signature and Date have no `id` and no `class`.** Nothing can read them.
   They are typed into and discarded - not saved, not exported, not printed
   back. This is the same fault the client found in Credit Cards and New Credits
   ("Airtel Name is not populated but amt populated"): a box on the form wired to
   nothing. It survived that fix because that round only covered the repeating
   rows in sections 4, 5 and 6.

So the calendar is the visible half; the invisible half is that whatever is
entered there does not exist as far as the app is concerned.

**Worth deciding at the same time:** should Verified By / Signature / Date be
*captured* at all, or are they there purely to be signed by hand after printing?
The station's own reference blank leaves all three empty for a pen. If they are
meant to be signed on paper, the right fix is to make them print-only rather
than to wire them up.

**Not changed.** The client asked for no changes while testing.

---

## 6. "Query cannot find the SEP14 data" — NOT a Query fault; the day saved as 24-Sep

**Client:** *"Search or Query not finding the Sep 14th data at all, to see it
again."*

**The data is not lost.** The demo database holds exactly one entry, and it is
dated today:

```
#1   2026-09-24   12BC4523V-RD   by=owner   mode=manual   netbal=27777.06
```

There is no 14-Sep record, so Query is behaving correctly - it is reporting the
truth. The day that was keyed went in under **2026-09-24**.

**Why.** Shift Date defaults to today on load
([screen.js:1285](../frontend/src/renderer/screens/daily-sales-entry/screen.js#L1285)):

```js
$("shift-date").value = new Date().toISOString().slice(0, 10);
```

and it is one field among several at the top of the form. Nothing about the
screen makes it obvious that the date is the thing which files the whole day, so
a day keyed *for the 14th* lands on the 24th and only shows up as "Query cannot
find it" later.

This is the third time the shift date has caused trouble: the SEP15 import
offered 14-Sept from the sheet header (the shift START) when the Trial Balance
wanted the 15th, and an earlier round saved a day as 2026-09-14 for the same
reason. The pattern is that the date is quietly decided FOR the operator and
quietly wrong.

**Options, for the client to choose:**

- Make Shift Date visually prominent - it is the key the entire day is filed
  under, and it currently looks like any other field.
- Warn on save when the shift date is not today and not the day being continued
  ("You are saving this as 14-Sep. Yesterday's entry was 13-Sep - correct?").
- Leave it, and rely on Query to spot it afterwards.

**Recovering this entry:** it is intact and can be moved to the right date by
loading it and changing Shift Date, or by an Owner correction - no data has to
be re-keyed. Say the word and I will move it.

**Not changed.** The client asked for no changes while testing.

---

## 7. A saved day's date cannot be corrected from the screen — OPEN, confirmed

**Client:** *"Data Date was set to Sep 24th and not able to update to Sep 14th -
how to correct it?"*

**Confirmed, and there is no path on the screen at all.** Changing Shift Date
makes the screen look for an entry on the NEW date; finding none it clears the
record being edited, so Save creates a SECOND entry on 14-Sep and leaves the
24-Sep one behind. There is no "move this day" action.

The API can do it - `PUT /daily-sales-entry/{id}` takes a new `shift_date` and
the change is audited - so correcting it is one call, not a re-key. The screen
simply never offers it.

This is the fourth problem traceable to the shift date (see item 6). The station
will hit it the first time someone keys a day on the wrong date, which is likely,
because the date defaults to today and looks like every other field on the form.

**Not changed** - the client's data, and they have not said to move it.

---

## 8. "Export to Excel is not working" — it works; the FORMAT is the problem

**Client:** *"Export to Excel is not working"*, with
`SEP24/SVR-DSE-2026-09-24-12BC4523V-RD.xlsx` attached.

**The export did not fail.** Every figure keyed is in the file, names included:

```
Airtel C87   Xtra Power C88   4000627873 C90   Nani C139   18.98254 C141
1265.3 C75   27000 C77        22868.18 C245    7775 C246
gas_total 89020.54            net_bal 27777.06
```

**What is wrong is the shape of it**, which is what the client has been saying
since 2026-09-23 ("your current Excel format are NOT AT ALL good", "nothing to
offer at all"):

- it is a vertical list of `Section | Field | Value | Computed | field key` -
  a machine round-trip format, not a document anyone would read;
- **172 of its 245 rows are empty placeholders**: ten rows are reserved per
  repeating section whether or not they are used;
- a day that fits on one printed page runs to 249 rows.

It was built to be edited and re-imported, and it is good at that. It is useless
as something to look at, send, or file - which is what "export" means to the
client.

**The fix is now cheap**, because the DSR layout already exists
(`lib/dsr-form.js`, measured from the station's own blank and matching it to
1.9mm). Options:

- **Export the DSR form as a PDF** - the same thing the Print button produces,
  saved rather than printed. Almost certainly what is wanted.
- **Export an .xlsx laid out like the DSR form** - a real workbook in the
  station's own shape, if they need to edit it in Excel.
- **Keep the key/value sheet as well**, under a clearer name such as "Export for
  re-import", since the round-trip is genuinely useful and is what the Excel
  import reads back.

**Not changed.** The client asked for no changes while testing.

---

## 9. Round two — New Credit rate, a 422 on save, and what Move does

### 9a. New Credit Rate now follows the fuel type — FIXED

**Client:** *"In 5. Today New Credit(s), Rate should be 1. HS 2. MS by default,
same as Section 1 Gas Sale(s) rates only."*

A credit is fuel sold on account: the same litres at the same pump price. Typing
the rate again invites a figure that disagrees with the day's own sale. Typing
`1`, `1.Diesel` or `Diesel` now fills the HS rate; `2`, `2.Petrol` or `Petrol`
fills MS. Verified on the live screen: **105.36** and **117.70**, matching
Section 1.

It fills, it does not lock — an operator can still override, and a rate they
changed themselves is not overwritten when they correct the fuel type.

### 9b. "Save failed -> 422: [object Object],[object Object]" — TWO bugs, both fixed

**The message.** FastAPI reports a validation failure as a LIST of objects, one
per bad field. The app interpolated that list straight into a string, which
JavaScript renders as `[object Object],[object Object]`. So the app knew exactly
what was wrong and told the operator nothing. Errors now read
`field: reason; field: reason`.

**The failure behind it, which is older and worse.** The 422 came from
`/daily-sales-entry/calc`, the authoritative recompute. `readForm()` builds the
whole SAVE payload - pump, date, pump status - and `CalcRequest` forbids unknown
fields (deliberately: a mistyped field name once silently dropped Rs 2,525). So
every recompute was rejected.

It was invisible because the call sits in `catch { }` with the comment *"keep the
mirror result on transient failure"*. It was not transient - it failed every
time - so **the screen has been showing figures from the renderer mirror, never
the engine**. The mirror is meant to be a responsive stand-in until the server
answers (SDD 6.4/7.3), not the thing you read. Saving always used the server, so
stored figures were never wrong; the displayed ones had no second opinion.

Now the calc payload carries only what `/calc` accepts, and a failed recompute
says so on screen instead of hiding behind the mirror.

### 9c. What the Move button does — it is item 7

**Client:** *"What is this Move button? And for what?"*

It is the fix for the problem reported earlier as *"Data Date was set to Sep 24th
and not able to update to Sep 14th - how to correct it?"*

It appears only when **a saved day is loaded and the date is changed to one with
nothing saved**. Without it, changing the date makes Save create a SECOND entry
and orphan the first - there was no way to re-file a day at all.

Pressing it re-files that entry under the new date. The figures are untouched,
nothing is re-keyed, and the change is written to the audit log.

If the bar appears when it is not wanted, ignore it - it does nothing until
pressed, and changing the date back makes it disappear.

---

## 10. Round three — Trial Balance derivations, and eight form items

All Trial Balance claims below were checked against the client's own
`SEP15/Trail_balance_15SEP2026.xlsx`, tab SEP15, reading the FORMULAS rather
than the values. Every one of them is right.

### 10a. Fields that must be derived, not typed — CONFIRMED against the sheet

| Line | Sheet | Formula | Today |
|---|---|---|---|
| 4.4 Today Reported | `D52` | `= D47` (3.15 Total Cash/Book Amount) | typed |
| 4.5 Diff | `D53` | `= D52 - D51` | derived, but stale on screen |
| 6.1 Today's Actual Reported | `D72` | `= D52` (4.4) | typed |
| 7.2 Today's Profit incl 2T | `D77` | `= K4` (Section 1 Total Sale Amt) | typed |
| 7.3 Today's Projected TB | `D78` | `= D76 + D77` (7.1 + 7.2) | wrong |
| 7.4 Difference | `D79` | `= D74 - D78` (Net Worth - Projected) | wrong |
| 7.5 Today's Actual Reported TB | `D80` | `= D78 + D79` | wrong |
| 8.2 Sales after expenses | `D83` | `= D50` (4.2) | typed |
| 8.3 Projected Cash/Book | `D84` | `= D82 + D83` (= 4.3) | typed |
| 8.5 Difference | `D86` | `= D85 - D84` | check |
| 8.8 Cash Value Difference | `D95` | `= D86 + D88` | check |

The pattern: the station's sheet computes these; our form asks the operator to
type them. A typed figure that should be derived is a figure that can disagree
with the day it came from - which is exactly what the client saw when 4.5 kept
showing -2,305,795.10 after 4.4 was corrected.

### 10b. Other Trial Balance faults reported

- **4.5 did not update after 4.4 was saved** - still showed -2,305,795.10.
- **Total Old Credit Collections does not update after save.**
- **Credit Given on Date has no calendar** (same fault as items 3 and 5).
- **The Difference reconciliation block (4.8-4.10) "is not needed"** - see the
  question below; this one I have NOT acted on.

### 10c. Daily Sales Entry / Summary items

- **Name and Mgr Name** auto-fill from the signed-in user. They should be a list:
  Sriharsha, Girish, Gopi, Mithendra.
- **Credit Cards needs a Card Type list**, with a "+" to add - as the Trial
  Balance dropdowns work.
- **Switching pump does not clear the form.** Data keyed for the Road pump stays
  on screen when the Office pump is selected and has to be cleared by hand. This
  is a data-integrity risk, not just an annoyance: the wrong pump's figures are
  one Save away from being filed under the other.
- **The printed entry form runs to two pages** and should fit A4 portrait -
  sections 3-6 can lose row height.
- **Export DSR PDF alignment** needs adjusting.
- **Daily Sales Summary has no Save button**, and no way to correct an entry.

### THE ONE QUESTION I HAVE NOT GUESSED AT

The client says the **Difference reconciliation block is not needed** (snapshot:
4.8 Difference Amount, 4.9 Yes Bank Return, 4.9a Staff Salaries, 4.9b RTGS,
4.9c Other Adjustment, 4.10 Total Difference).

That block is what Close & Sign Off tests. It was built on 2026-09-16 from the
client's OWN SEP16 panel (`F54:F57`), because without it SEP16 reads -37,578.64
against a true -20.64 and the day cannot be closed. Removing it means the Rs 50
escalation goes back to testing 4.5, and SEP16-shaped days get blocked.

So: remove the block and revert the escalation to 4.5, or keep it? I have left
it exactly as it is until they say.

---

*(further items appended as they are reported)*
