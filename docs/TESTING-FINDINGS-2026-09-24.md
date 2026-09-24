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

*(further items appended as they are reported)*
