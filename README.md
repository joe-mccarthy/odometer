# Odometer

[![CI](https://img.shields.io/github/actions/workflow/status/joe-mccarthy/odometer/ci.yml?branch=main&label=ci)](https://github.com/joe-mccarthy/odometer/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/github/actions/workflow/status/joe-mccarthy/odometer/coverage.yml?branch=main&label=coverage)](https://github.com/joe-mccarthy/odometer/actions/workflows/coverage.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB)](pyproject.toml)
[![Release](https://img.shields.io/github/v/release/joe-mccarthy/odometer?label=release)](https://github.com/joe-mccarthy/odometer/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-2496ED)](Dockerfile)

**Odometer** is a local-first CLI and TUI application for tracking the true cost of owning a vehicle.

> Status: v0.1.0 is the first GitHub-only testing release. Odometer is still
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
- Extensible for a future web/API layer

No cloud. No accounts. No subscriptions. Your data stays with you.

## v0.1.0 Features

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
- Docker and Docker Compose support

## Run Locally from Source

```bash
poetry install
poetry run odometer --help
```

Initialise a local development database:

```bash
poetry run odometer init
```

## Basic Usage

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

## CLI Commands

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
```

Docker stores data in `./data` on the host and `/data/odometer.db` in the container.

## Data Storage

By default, Odometer stores one SQLite database named `odometer.db` in the local user data directory for the current operating system.

Show the active paths:

```bash
poetry run odometer config show
```

## Environment Variables

- `ODOMETER_DB_PATH`: override the SQLite database path.

Example:

```bash
ODOMETER_DB_PATH=./odometer.db poetry run odometer init
```

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

## v0.1.0 Scope

The v0.1.0 release includes:

- Core CLI commands for vehicles, expenses, fuel logs, summaries, and calculations.
- SQLite-backed local storage with Docker support.
- Running and ownership cost calculations, UK MPG, rolling averages, category
  breakdowns, and monthly or annual summaries.
- Textual TUI screens for dashboard, vehicles, vehicle detail, expenses, fuel,
  and summaries.
- Vehicle-scoped TUI context, confirmed deletion flows, and terminal bar charts
  for monthly spend and mileage.

## Licence

Odometer is open source and licensed under the GNU General Public License v3.0 (GPL-3.0).

See the [LICENSE](LICENSE) file for details.
