# Local dashboard verification

Use a disposable database, never your everyday database. With project Python dependencies installed:

```sh
ODOMETER_DB_PATH=/tmp/odometer-ui-smoke.sqlite odometer web --port 8876
```

Start from a new database path. In a second terminal, install browser test tooling outside the repository (no Node runtime or build step is required for the application):

```sh
npm install --prefix /tmp/odometer-browser-tests playwright @axe-core/playwright
/tmp/odometer-browser-tests/node_modules/.bin/playwright install chromium
NODE_PATH=/tmp/odometer-browser-tests/node_modules node tests/browser/dashboard.cjs
```

The script creates and deletes its own vehicle on `http://127.0.0.1:8876`; it expects an initially empty database. It checks real API integration, full/partial/full UK MPG, integer-pence GBP, validation preservation, safe rendering, cancel/confirm deletion and vehicle cascade, keyboard entry, mobile overflow, and absence of external requests. It runs an axe WCAG A/AA scan at mobile and desktop sizes. It does not alter server or shared service code.

Manual smoke steps:

1. Open the URL at 390px and desktop widths. Tab from the skip link through the context selector, forms and buttons. Check visible focus, input labels, and screen reader save/error announcements.
2. Add two vehicles with distinct registrations, initial mileage and tank capacities. Select each, add fuel and expenses, switch rapidly between vehicles and verify the visible context matches every record. Refresh and confirm persistence.
3. Enter GBP `45.01`, and check it displays as £45.01 after saving. More than two decimal places must be rejected. Try backwards fuel mileage or an oversized fill: entered values remain and a readable error appears. Do not blindly retry an uncertain save after a connection failure; refresh first.
4. Add full/partial/full fills and check UK MPG becomes available only after a closed segment. A fleet summary never shows a fleet MPG. Zero spending and unavailable cost-per-mile remain distinct.
5. Inspect monthly summaries with another year; all-time totals, annual totals and category totals retain their scope. Include archived/sold vehicles, mark a vehicle sold or archived and verify it reappears with the filter enabled. Update tank capacity and add a subsequent fill.
6. Cancel then confirm record deletion. Cancel then confirm vehicle deletion; its warning names the registration and all fuel/expense records. Verify the selected context returns safely to fleet.
7. Stop the server and refresh: the error state must be readable. Restart and use Refresh. Check browser network requests stay on the local origin. Confirm ordinary CLI/TUI reads see saved browser records using this same disposable database.

Pagination regression: seed a disposable database using `seed` in
`tests/test_history_pagination.py`, add an empty vehicle registered `EMPTY 2`,
and serve it on port 8877. Run `node tests/browser/pagination.cjs` with the same
NODE_PATH. This traverses 1,205 records per kind, checks bounded responses, tied
dates, independent filters, invalid ranges, context resets, keyboard controls,
320px layout, axe and local-only requests.


Download regression: start the app with disposable data on port 8878 and run
`NODE_PATH=/tmp/odometer-browser-tests/node_modules node tests/browser/downloads.cjs`.
This checks file bytes and names, all five choices, keyboard focus, accessible
failures, 320px reflow, scoped axe and local-only requests.

## Reminders (#9)

Against a disposable empty database, run `tests/browser/reminders.cjs` with
`NODE_PATH` pointing to Playwright and @axe-core/playwright. `PORT` defaults to
8765; configure `create_app(..., port=PORT)` to match. Covers create, thresholds,
validation/draft retention and retry, edit, complete with/without a linked next
occurrence, completed history, cancel-first deletion, sold/inactive visibility,
focus, 320px reflow, scoped axe and absence of external requests. Python
`tests/test_reminders.py` fixes the calendar for 30-day/1,000-mile and 90-day
staleness boundaries, missing/baseline/provenance, rollback/concurrent retry,
CLI/API and real downloaded SQLite retention. Manual assistive-technology and
cross-browser checks remain separate.
Limits: reactivation and browser JSON import are outside this release. CLI JSON import is supported. Automated Chromium and axe supplement independent acceptance and manual assistive-technology testing.

## Review repair regressions

From the repository root, start a fresh disposable fixture (refuses existing files):

```sh
ODOMETER_DB_PATH=/tmp/odometer-review-repairs-new.sqlite PYTHONPATH=. poetry run python tests/browser/review-repairs-server.py
```

Then run `NODE_PATH=/tmp/odometer-browser-tests/node_modules node tests/browser/review-repairs.cjs`.
It checks exact prefills and raw numeric JSON writes for 9,007,199,254,740,990,
9,007,199,254,740,993 and SQLite's maximum signed integer pence in both editors;
unchanged imported null fuel prices; safe changed-amount validation; overlapping
fuel/expense IDs; and focus fallback when a corrected expense leaves the current
filter or first page. It also checks 320px operation and local-only requests.
Use a new fixture database for each run. Run `dashboard.cjs` separately against
its empty disposable server on :8876 to verify cancel/confirm deletion with the
existing `#expense-list button.danger` selector.

HTTP money fields remain JSON integers. Fuel/expense responses additionally carry
`total_cost_pence_exact` / `amount_pence_exact` decimal strings so browser edit
prefills never depend on a rounded JavaScript Number. Unchanged amounts are sent
as exact JSON integer tokens; changed browser amounts retain the existing safe
integer limit. API and TUI callers retain their integer-pence contracts.
Fuel updates preserve an omitted unit price when cost and quantity are unchanged
(including an imported null); changing either derives a new price unless an
explicit non-null price is supplied. Explicit null requests recalculation.
