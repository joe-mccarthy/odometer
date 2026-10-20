# Odometer

[![CI](https://img.shields.io/github/actions/workflow/status/joe-mccarthy/odometer/ci.yml?branch=main&label=ci)](https://github.com/joe-mccarthy/odometer/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/github/actions/workflow/status/joe-mccarthy/odometer/coverage.yml?branch=main&label=coverage)](https://github.com/joe-mccarthy/odometer/actions/workflows/coverage.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB)](pyproject.toml)
[![Release](https://img.shields.io/github/v/release/joe-mccarthy/odometer?label=release)](https://github.com/joe-mccarthy/odometer/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-2496ED)](Dockerfile)

**Odometer** is a local-first CLI, TUI and browser application for tracking the true cost of owning a vehicle.

> Status: v0.2.0 is a GitHub-only testing release. Odometer is still
> early-stage software and is not published to PyPI yet.

It helps you answer a simple question:

> What does this car actually cost me?

Odometer records fuel, servicing, insurance, tax, repairs, finance, tyres, parking, tolls, fines, and other ownership costs. It calculates total spend, cost per mile, UK MPG, rolling averages, and monthly or annual summaries.

## Philosophy

Odometer is designed to be:

- Local-first
- Privacy respecting
- Multi-vehicle
- CLI-first
- TUI included
- Docker-friendly
- Local browser dashboard with a shared service-backed API

No cloud. No accounts. No subscriptions. Your data stays with you.

## Features

- Vehicle management by UK registration
- Expense logging by category
- Fuel logging with litres, mileage, station, and full/partial fills
- SQLite storage using an OS-appropriate local data directory
- `ODOMETER_DB_PATH` override for tests, Docker, and portable use
- GBP money handling using integer pence
- UK MPG calculations using imperial gallons
- Running and ownership cost per mile
- Rolling averages
- Category breakdowns
- Monthly and annual summaries
- Textual TUI dashboard, tables, summaries, and terminal bar charts
- Docker and Docker Compose support for CLI/TUI
- Local browser dashboard and shared service-backed API
- JSON/CSV exports and online SQLite backups

## Run Locally from Source

You need Python 3.12 or newer (below 4.0), Git, and Poetry 2.4.x. The project is
not published to PyPI; run it from this repository.

```bash
git clone https://github.com/joe-mccarthy/odometer.git
cd odometer
poetry install
poetry run odometer --help
```

Initialise your local database:

```bash
poetry run odometer init
```

## Basic Usage

Amounts such as `--amount` and `--purchase-price` are in GBP pounds, mileage is
in miles, and fuel quantities are in litres. Enter the complete odometer reading
for `--mileage`, rather than the distance travelled since the last record.
Expense and fuel dates default to today; use `--date YYYY-MM-DD` for older records.
Vehicle registrations are normalised, so `"AB12 CDE"` can be used as `AB12CDE`.

Add a vehicle:

```bash
poetry run odometer vehicle add \
  --registration "AB12 CDE" \
  --make Ford \
  --model Kuga \
  --year 2019 \
  --initial-mileage 42000 \
  --fuel-tank-litres 55 \
  --purchase-price 12500
```

Log an expense:

```bash
poetry run odometer expense add \
  --vehicle AB12CDE \
  --category service \
  --amount 249.99 \
  --mileage 43000 \
  --description "Annual service"
```

Log fuel:

```bash
poetry run odometer fuel add \
  --vehicle AB12CDE \
  --litres 45.2 \
  --amount 68.50 \
  --mileage 43420 \
  --station Tesco \
  --full
```

Fuel logs require the vehicle fuel tank size. Set it when adding the vehicle, with
`vehicle set-fuel-tank`, or with `fuel add --fuel-tank-litres` on the first fill.

Show a summary:

```bash
poetry run odometer summary --vehicle AB12CDE
```

## Understanding the Calculations

- **UK MPG** uses imperial gallons (4.54609 litres per gallon). The first full
  tank establishes a baseline; a later full tank at a higher mileage closes the
  first measurable segment. Partial fills between them are included. Use
  `fuel add --partial` when you do not fill the tank; fills default to `--full`.
- **Running cost per mile** divides recorded fuel and non-fuel expenses by miles
  driven since the vehicle's initial mileage. A later odometer reading is needed
  before a cost per mile can be calculated.
- **Ownership cost per mile** also includes the purchase price. It is available
  only when a purchase price is recorded; it does not estimate depreciation or
  subtract a resale value.

A single fuel log is enough to record spending, but it will not produce MPG yet.

## CLI Commands

Use `--help` on a command group or subcommand to see its options:

```bash
poetry run odometer vehicle --help
poetry run odometer fuel add --help
```

Common commands:

```bash
poetry run odometer config show
poetry run odometer vehicle list
poetry run odometer vehicle show AB12CDE
poetry run odometer vehicle set-fuel-tank AB12CDE --litres 55
poetry run odometer vehicle archive AB12CDE
poetry run odometer vehicle sold AB12CDE
poetry run odometer vehicle delete AB12CDE

poetry run odometer expense list --vehicle AB12CDE
poetry run odometer expense delete EXPENSE_ID
poetry run odometer fuel list --vehicle AB12CDE
poetry run odometer fuel delete FUEL_LOG_ID

poetry run odometer summary
poetry run odometer summary monthly --vehicle AB12CDE --year 2026
poetry run odometer summary annual --vehicle AB12CDE
poetry run odometer summary categories --vehicle AB12CDE

poetry run odometer calc mpg --vehicle AB12CDE
poetry run odometer calc cost-per-mile --vehicle AB12CDE
```

Dedicated fuel logs are the preferred way to record fuel. `FUEL` expenses are supported, but when fuel logs exist for the same scope, Odometer uses fuel logs as the source of truth to avoid obvious double counting.

## TUI Usage

Start the terminal interface:

```bash
poetry run odometer tui
```

The TUI includes:

- Dashboard
- Vehicle overview
- Vehicle detail
- Expense table
- Fuel log table
- Summary tables
- Monthly spend and mileage bar charts

Use the footer shortcuts to move between screens. When more than one vehicle exists,
dashboard, expense, fuel, and summary screens include a vehicle context selector so you
can switch between one vehicle and all vehicles. With a single vehicle, Odometer hides
that selector and scopes those screens to the only vehicle automatically. Press `a` on
vehicle, expense, or fuel screens to add records. Press `delete` on vehicle, expense, or
fuel screens to delete the selected row after confirmation.

## Local Browser Usage

After `poetry install`, start the browser dashboard:

```bash
poetry run odometer web
```

Open `http://127.0.0.1:8765`. The foreground server initialises the configured
SQLite database, binds only IPv4 loopback and stops with Ctrl+C. Use
`poetry run odometer web --port 8876` for another local port. CLI, TUI and web
share the database selected by `ODOMETER_DB_PATH`; use a disposable path when
trying the app. No Node build, account, remote assets or cloud service is needed.
Host/origin checks protect browser mutations; reverse proxies and LAN hosting
are unsupported. Any process running as your local user can access your data.

The dashboard supports vehicle context, fuel and expenses, summaries, tank updates,
sold/archive status and confirmed deletion. Money entry is GBP; storage remains
integer pence. MPG uses full-to-full imperial gallons including intervening partial
fills. Export and online backup are available through the CLI commands below.

Current limits: record lists show at most the newest 1,000 rows; no
reactivation, import or browser export/backup controls are provided.
Chromium has been tested; Firefox/WebKit, native devices, screen readers and large
datasets remain unverified. See [browser smoke steps](tests/browser/smoke.md).
Before a manual file-copy backup or restore, stop the web server as well as CLI/TUI
sessions. The `backup` command supports a running database through SQLite online
backup; restore only while all Odometer processes are stopped.

## Docker Usage

Build the image:

```bash
docker compose build
```

Run commands:

```bash
docker compose run --rm odometer --help
docker compose run --rm odometer init
docker compose run --rm odometer vehicle list
docker compose run --rm odometer tui
```

Docker stores data in `./data` on the host and `/data/odometer.db` in the container.

## Data Storage

By default, Odometer stores one SQLite database named `odometer.db` in the local user data directory for the current operating system.

Show the active paths:

```bash
poetry run odometer config show
```

### Backups

Prefer `poetry run odometer backup odometer-backup.db`, which safely snapshots a
running database. See the export and backup commands below. For a manual copy or
restore, stop all CLI, TUI and web processes first. Docker Compose stores the file
at `./data/odometer.db`. Restore by replacing the configured database while all
processes are stopped, or point `ODOMETER_DB_PATH` at a copy of the backup.

### Portable exports and SQLite backups

These commands read the configured local database (`ODOMETER_DB_PATH` applies),
include inactive vehicles, and never overwrite an existing destination. Initialise
new databases with `poetry run odometer init` first. Destination parent directories must exist.

```bash
poetry run odometer export json odometer-export.json
poetry run odometer export csv vehicles vehicles.csv
poetry run odometer export csv fuel fuel.csv
poetry run odometer export csv expenses expenses.csv
poetry run odometer backup odometer-backup.db
```

JSON format version 1 contains `format_version`, `vehicles`, `fuel`, and `expenses`.
Records retain identifiers, relationships, timestamps, dates, nulls and all model
fields. Monetary totals remain integer pence; fractional fuel unit prices retain
their stored precision. CSV uses the same field names, ISO dates, lowercase
booleans and empty cells for nulls (CSV cannot distinguish null from empty text).
Exports contain raw records rather than calculated totals: fuel-category expenses
and fuel logs remain separate, preserving existing reporting deduplication rules.
No import command is provided.

Each export reads a consistent SQLite snapshot. Backups use SQLite's online backup
API, include committed WAL data, and pass `PRAGMA integrity_check` before publication.
They are standalone SQLite files, suitable for opening with SQLite or using as an
`ODOMETER_DB_PATH`. Commands never initialise or migrate the source database. Output
is created locally with owner-only permissions; exports and backups contain your
private records, so choose their storage location accordingly. Publication requires
a filesystem supporting hard links in the destination directory.

## Environment Variables

- `ODOMETER_DB_PATH`: override the SQLite database path.

Example:

```bash
export ODOMETER_DB_PATH="$PWD/odometer.db"
poetry run odometer init
poetry run odometer tui
```

This shell syntax is for Bash and similar shells. In PowerShell, set
`$env:ODOMETER_DB_PATH = "$PWD/odometer.db"` before running the same Poetry commands.
Keep the override set for subsequent commands to use the same database.

## Developer Setup and Contributing

Prerequisites:

- Python 3.12 or newer
- Poetry 2.4.x
- Docker, if you want to test the container build

Set up a local development environment:

```bash
poetry install
poetry run odometer --help
```

Use a project-local database while developing so you do not touch your normal Odometer data:

```bash
ODOMETER_DB_PATH=./odometer-dev.db poetry run odometer init
ODOMETER_DB_PATH=./odometer-dev.db poetry run odometer tui
```

Run the same core checks used by pull request CI:

```bash
poetry check --lock
poetry run ruff format --check .
poetry run ruff check .
poetry run mypy odometer
poetry run pytest
```

For a walkthrough of the package structure, data flow, business rules, and tests,
see [docs/CODEBASE.md](docs/CODEBASE.md).

Generate coverage reports:

```bash
poetry run pytest --cov=odometer --cov-report=term-missing --cov-report=xml --cov-report=html
```

The HTML report is written to `htmlcov/`, and the XML report is written to `coverage.xml`.

Check the Docker image locally:

```bash
docker compose build
docker compose run --rm odometer --help
```

Contribution guidelines:

- Keep changes focused and covered by tests when they affect behavior.
- Prefer the existing service, repository, CLI, and TUI patterns before adding new abstractions.
- Run formatting, linting, type checking, and tests before opening a pull request.
- Update this README or the changelog when behavior, commands, or release process details change.

GitHub Actions run pull request checks for formatting, linting, typing, tests,
coverage artifacts, and Docker builds. Releases are created as GitHub Releases
from version tags in the form `vX.Y.Z`; the tag version must match the version
in `pyproject.toml`.

Odometer is GitHub-only while release testing is in progress. The release
workflow builds distribution artifacts, uploads checksums, and publishes a
GitHub Release. It does not publish to PyPI.

## Release Scope

The release includes:

- Core CLI commands for vehicles, expenses, fuel logs, summaries, and calculations.
- SQLite-backed local storage with Docker support.
- Running and ownership cost calculations, UK MPG, rolling averages, category
  breakdowns, and monthly or annual summaries.
- Textual TUI screens for dashboard, vehicles, vehicle detail, expenses, fuel,
  and summaries.
- Vehicle-scoped TUI context, confirmed deletion flows, and terminal bar charts
  for monthly spend and mileage.

## Licence

Odometer is open source and licensed under the GNU General Public License v3.0 only (GPL-3.0-only).

See the [LICENSE](LICENSE) file for details.


Correct records with `odometer fuel edit RECORD_ID --amount 45.01 --partial`
or `odometer expense edit RECORD_ID --amount 12.34 --clear-mileage`.
Only supplied CLI fields change; pass an empty string to clear optional text.
The browser offers Edit beside each record, and the TUI uses `e` on a selected row.
Corrections preserve IDs and vehicle relationships and validate neighboring fuel readings.
HTTP clients can replace editable fields with `PUT /api/fuel/{id}` and
`PUT /api/expenses/{id}` using the same local Origin and request headers as creation.
