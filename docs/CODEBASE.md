# Codebase Guide

This guide explains how Odometer is put together and where to look when you want
to understand or change a feature. It is written as a map of the code rather than
API reference documentation.

## Reading Order

If you are new to the project, read the code in this order:

1. `odometer/models/` to understand the stored data.
2. `odometer/services/` to understand the business rules.
3. `odometer/repositories/` to understand how data is queried and saved.
4. `odometer/cli/` to see how commands call the service layer.
5. `odometer/tui/app.py` to see how the TUI gathers data for screens.
6. `odometer/tui/screens/` to see how each terminal screen is rendered.
7. `tests/` to see expected behaviour and edge cases.

## High-Level Shape

Odometer is a local-first Python application. It stores data in SQLite with
SQLModel, exposes command-line commands with Typer, and exposes a terminal UI
with Textual.

The code is intentionally layered:

```text
CLI commands and TUI screens
        |
        v
Application/service methods
        |
        v
Repositories
        |
        v
SQLModel models and SQLite
```

The important rule is that validation and business behaviour belong in services,
not in the CLI or TUI. The CLI and TUI are presentation layers.

## Package Map

`odometer/models/`

Defines the database tables and enum values. These classes are SQLModel models,
so they describe both Python objects and SQLite tables.

`odometer/repositories/`

Contains low-level persistence operations. Repositories build SQLModel queries,
apply filters, control sort order, and commit deletes or saves. They do not own
business validation.

`odometer/services/`

Contains business logic. Services validate input, resolve vehicles by id or
registration, calculate costs, prevent invalid fuel logs, avoid obvious fuel
double-counting, and coordinate multi-table operations such as deleting a
vehicle and its related data.

`odometer/cli/`

Contains Typer command groups. Commands parse command options, open a database
session, call services, and print Rich tables or messages.

`odometer/tui/`

Contains the Textual app. `OdometerTUI` in `odometer/tui/app.py` acts as the TUI
controller: it opens sessions, calls services, builds screen data objects, tracks
the selected vehicle context, and exposes add/delete methods for screens.

`odometer/tui/screens/`

Contains individual Textual screens and modal dialogs. Screen classes compose
widgets, keep selected table row ids, call `OdometerTUI`, and refresh widgets.

`odometer/tui/widgets/`

Contains small reusable Textual widgets such as metric cards and terminal bar
charts.

`odometer/db/`

Contains database path, engine, session, and bootstrap helpers. It also contains
small SQLite schema update code for existing local databases.

`odometer/utils/`

Contains small formatting and parsing helpers for money, dates, mileage,
registration strings, and display values.

`tests/`

Contains service, CLI, and TUI tests. These are the best examples of expected
behaviour because they create realistic vehicles, expenses, and fuel logs.

## Data Model

### Vehicle

`Vehicle` is the root entity. Expenses and fuel logs point at a vehicle through
`vehicle_id`.

Important fields:

- `registration`: display registration, stored uppercase.
- `normalised_registration`: lookup registration with spaces removed.
- `initial_mileage`: baseline mileage for cost and mileage calculations.
- `fuel_tank_litres`: required before adding fuel logs.
- `purchase_price_pence`: optional purchase cost for ownership cost per mile.
- `status`: `ACTIVE`, `SOLD`, or `ARCHIVED`.

Only one active vehicle can exist for a normalised registration. Historical sold
or archived vehicles can still have the same registration.

### Expense

`Expense` records non-fuel ownership costs such as service, MOT, insurance,
repair, parking, and fines. The `FUEL` category exists for compatibility and
manual use, but dedicated fuel logs are preferred.

Amounts are stored as integer pence, never floats.

### FuelLog

`FuelLog` records fuel fill-ups with litres, total cost, odometer reading,
station, and whether the fill was full or partial.

Fuel logs are the source of truth for fuel spend when any fuel logs exist for a
scope. This avoids counting the same fuel twice if a user also entered a fuel
expense.

## Database Flow

The active database path comes from `ODOMETER_DB_PATH` when set. Otherwise it
uses an operating-system-specific app data directory from `platformdirs`.

Common flow:

```text
CLI/TUI action
  -> initialise_database()
  -> get_session()
  -> service method
  -> repository query/save/delete
  -> SQLite
```

`initialise_database()` creates missing tables with SQLModel metadata. It also
applies lightweight SQLite schema updates for known local database changes.
There is not a full migration framework yet.

## Services

### VehicleService

Owns vehicle lifecycle behaviour:

- create vehicles
- prevent duplicate active registrations
- resolve vehicles by id or registration
- list active or inactive vehicles
- set fuel tank capacity
- mark vehicles archived or sold
- delete vehicles and cascade-delete expenses and fuel logs

Deleting a vehicle is coordinated here because it spans three tables. The
expense deletes, fuel deletes, and vehicle delete are committed together.

### ExpenseService

Owns expense validation:

- vehicle must resolve successfully
- amount must be greater than zero
- mileage, when supplied, cannot be below the vehicle initial mileage
- category input is parsed into `ExpenseCategory`

It also lists expenses by optional vehicle, category, date range, limit, and sort
direction.

### FuelService

Owns fuel validation:

- litres and total cost must be greater than zero
- odometer mileage cannot be below initial mileage
- fuel odometer readings cannot go backwards for the same vehicle
- vehicle fuel tank capacity must be set
- litres cannot exceed the tank capacity

If `fuel_tank_litres` is supplied while adding a fuel log, the vehicle tank size
is saved first, then the fuel log is recorded.

### CalculationService

Owns reusable calculations:

- latest known mileage
- miles driven
- spend split between fuel and non-fuel costs
- running and ownership cost per mile
- full-to-full UK MPG segments with partial fills accumulated inside closed segments
- category breakdowns
- monthly and annual summaries
- rolling average monthly spend

For MPG, only full-to-full segments are reported. Partial fills after a starting
full tank are accumulated, then included when a later full tank closes the
segment. Partial fills before the first full tank are ignored for MPG because
there is no known starting fuel level.

For period mileage, the service finds the latest reading before the period and
compares it with the latest reading inside the period. If a vehicle has no
reading in a period, mileage for that vehicle is reported as unavailable for that
period.

### SummaryService

Provides higher-level summary methods used by the CLI and TUI. It delegates most
math to `CalculationService`, then packages results into objects that are easier
for presentation code to consume.

## CLI Flow

The command entry point is `odometer/main.py`, which exports the Typer app from
`odometer/cli/app.py`.

`odometer/cli/app.py` registers command groups:

- `config`
- `vehicle`
- `expense`
- `fuel`
- `summary`
- `calc`

Most commands follow this shape:

```text
parse Typer arguments
  -> with cli_session() as session
  -> call a service
  -> catch expected Odometer errors
  -> print a message or Rich table
```

Delete commands ask for confirmation before calling the service delete method.

## TUI Flow

The Textual entry point is `OdometerTUI` in `odometer/tui/app.py`.

The app has two responsibilities:

1. Register and switch screens.
2. Convert service results into screen-friendly data objects.

The screen classes do not open database sessions directly. They call methods on
`OdometerTUI`, such as:

- `get_dashboard_data()`
- `get_vehicle_rows()`
- `get_vehicle_detail()`
- `get_expenses()`
- `get_fuel_logs()`
- `get_summaries_data()`
- `add_vehicle_from_form()`
- `add_expense_from_form()`
- `add_fuel_from_form()`
- `delete_vehicle()`
- `delete_expense()`
- `delete_fuel_log()`

This keeps database access in one place for the TUI.

### Vehicle Context

`OdometerTUI.selected_vehicle_id` stores the current TUI vehicle context. A value
of `None` means "all vehicles". A vehicle id means "only this vehicle".

The constant `VEHICLE_CONTEXT_ALL` is the select widget value for all vehicles.
`set_vehicle_context()` converts the select value into the internal state.

When the database contains exactly one vehicle, `OdometerTUI` treats that vehicle
as the effective context even when `selected_vehicle_id` is `None`. The shared
selector is hidden in that case because there is no meaningful choice between one
vehicle and all vehicles.

Dashboard, expenses, fuel, and summaries screens share the selector helpers in
`odometer/tui/screens/context.py`.

### TUI Tables

Tables use `replace_table_data()` from `odometer/tui/screens/tables.py`. That
helper clears and rebuilds the table, sizes each column to fit the loaded data,
and forces Textual to update dimensions immediately. That is why table columns
fit after reload without needing a manual `r` refresh.

### Delete Modals

Destructive TUI actions use `ConfirmDeleteModal`. The modal returns `True` only
when the Delete button is pressed. The calling screen performs the actual delete
in its callback.

## Important Business Rules

Money is integer pence.

All stored money values use integer pence to avoid floating-point rounding
errors. User-facing input and display convert between pounds and pence.

Registrations are normalised for lookup.

The display registration keeps readable spacing. The normalised registration
removes spaces and uppercases input so `AB12 CDE` and `ab12cde` resolve to the
same active vehicle.

Fuel logs beat fuel expenses for fuel spend.

If fuel logs exist in a calculation scope, fuel expenses are ignored for fuel
spend. Non-fuel expenses are still included.

Full-to-full fuel log segments are required for MPG.

The first full tank creates a starting point. The next full tank creates the
first MPG segment. Any partial fills between those two full tanks are included in
the segment litres.

Vehicle delete is cascading.

Deleting a vehicle deletes its expenses and fuel logs in the same service method.
This keeps the database from retaining orphaned ownership data.

## Tests

The tests are split by layer:

- `tests/test_vehicle_service.py` covers vehicle lifecycle and cascading delete.
- `tests/test_expense_service.py` covers expense validation and deletion.
- `tests/test_fuel_service.py` covers fuel validation, tank size, and ordering.
- `tests/test_calculation_service.py` covers cost, MPG, period, and breakdown math.
- `tests/test_summary_service.py` covers summary aggregation.
- `tests/test_cli.py` covers command-line flows.
- `tests/test_tui_screens.py` covers TUI screen rendering, vehicle context,
  fitted tables, modals, and delete flows.

Tests use a temporary SQLite database by setting `ODOMETER_DB_PATH` in
`tests/conftest.py`. That keeps tests isolated from your real local data.

Run the full suite with:

```bash
poetry run pytest
```

Run the quality checks with:

```bash
poetry run ruff format --check odometer tests
poetry run ruff check odometer tests
poetry run mypy odometer
```

## Adding a Feature

For a data-backed feature, the usual order is:

1. Add or update the model if new stored fields are needed.
2. Add repository queries only if the existing list/get methods are not enough.
3. Add service behaviour and validation.
4. Expose it in the CLI or TUI.
5. Add tests at the lowest useful layer.

Prefer service tests for business rules. Add CLI or TUI tests when presentation
behaviour matters, such as command output, screen context, modals, or table rows.

## Common Debugging Pointers

Unexpected data path:

Check `ODOMETER_DB_PATH` and `odometer/db/session.py`.

Vehicle not found:

Check registration normalisation and whether the vehicle is inactive. Some
methods only return active vehicles.

Fuel log rejected:

Check tank size, litres, initial mileage, and whether the odometer reading goes
backwards compared with the latest fuel log.

Summary looks too high:

Check whether both fuel expenses and fuel logs exist. Fuel logs should win for
fuel spend when present.

TUI table looks stale:

Check whether the screen calls `refresh_table()` or `refresh_screen()` after the
action callback. Shared table rebuild behaviour lives in
`odometer/tui/screens/tables.py`.
