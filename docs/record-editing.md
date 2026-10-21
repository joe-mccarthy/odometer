# Record corrections (GitHub #5)

Criteria: 5.1–5.4 in the product acceptance matrix.

- Shared `FuelService.update_fuel_log(id, **changes)` and
  `ExpenseService.update_expense(id, **changes)` preserve IDs, vehicle IDs and
  creation timestamps. Unknown fields and empty updates are rejected. Supplied
  nullable fields clear values; omitted fields retain them. Validation runs on
  detached candidates before persistence.
- Fuel cost/quantity corrections derive a fresh price unless explicitly
  overridden. Whole-history validation checks initial mileage, positive finite
  litres/prices, positive integer pence, tank capacity and chronology in date/ID
  order, including both neighbors. Equal mileage is allowed. Creation behavior
  remains unchanged. Corrections supply persisted baseline history: an existing
  descending adjacent pair is tolerated only while both IDs, dates and mileages
  remain identical. New or changed conflicts are rejected. Unrelated notes or
  cost corrections therefore remain possible on legacy same-day histories.
- Import integration: `validate_fuel_history(vehicle, complete_candidate_rows)`
  in `odometer.services.history_validation` performs no database writes. Pass
  all final rows for each vehicle in any input order, before committing an import
  transaction; do not call append-only creation for historical imports. Imports
  omit the optional baseline and retain strict complete-history validation.
- HTTP: PUT `/api/fuel/{id}` and `/api/expenses/{id}` accept complete editable
  creation fields, excluding vehicle/tank changes. Existing host, origin,
  request-header and bounded-body guards apply; PUT requires JSON content type.
- CLI: `fuel edit ID` / `expense edit ID` change supplied options only. GBP uses
  the existing shared parser and integer-pence storage. Empty optional strings
  clear text; `--clear-mileage` clears optional expense mileage. Empty or non-text
  categories raise an actionable domain validation error before any write.
- Corrections reject non-finite derived unit prices before persistence.
- TUI: `e` opens the selected record prefilled, with vehicle fixed. Save uses
  shared services; invalid drafts stay open, Cancel/Escape writes nothing.
  Blank dates in edits are required-field errors; additions retain today as the
  default. If a selected row disappears before opening, refresh and report it.
- Browser: Edit precedes Delete, with a named native dialog, GBP values, retained
  errors, in-dialog dirty-discard confirmation, duplicate-save guard, refreshed
  records/metrics and focus restoration. Confirmed-save refresh failure gets a
  distinct status message. Assets and requests stay local.

## Integration

Base: `be9f66862d04be32babb8a4392828d568b13b5fb` (main). No dependency commits.
Land this shared contract before integrating #8 import candidate validation.
Browser #6/#10/#11/#12 changes also touch `app.js`; retain record actions and
invoke the common `load` refresh after successful corrections. Product defaults
for pagination/reminders belong to their respective issues.

## Executed evidence

- `tests/test_record_editing.py`: domain, CLI invocations and Textual pilot
  prefill/rejection/save/cancel tests. Includes backdated corrections, both
  neighbors, same-date ID ordering, equal mileage, money, nulls and derived MPG.
- `tests/test_web_api.py`: PUT identity, corrected summary spending, full/partial
  MPG availability, invalid/missing/extra fields and local boundary protection.
- `tests/browser/editing.cjs`: Chromium 156 at 320×800; prefill, retained invalid
  draft and focused error, save, spending refresh, record focus restoration,
  dirty Escape discard with unchanged expense, no page overflow, no external
  requests and no JavaScript errors. Run against a disposable database/server on
  127.0.0.1:8899 with `create_app(port=8899)` and temporary Playwright tooling.
- Ruff lint/format and mypy passed. Full pytest results and exact PR head/CI
  are recorded on the implementation task and PR.

Manual screen-reader, Firefox/WebKit and zoom checks remain unassessed. This
implementation evidence is not independent review or CEO product acceptance.
