# Odometer

![Python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square)
![License](https://img.shields.io/github/license/joe-mccarthy/odometer?style=flat-square)
![Issues](https://img.shields.io/github/issues/joe-mccarthy/odometer?style=flat-square)
![Latest Commit](https://img.shields.io/github/last-commit/joe-mccarthy/odometer?style=flat-square)

**Odometer** is a local-first CLI and TUI application for tracking the true cost of owning a vehicle.

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

## Features Implemented

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

## Install Locally with Poetry

```bash
poetry install
poetry run odometer --help
```

Initialise the database:

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

poetry run odometer expense list --vehicle AB12CDE
poetry run odometer fuel list --vehicle AB12CDE

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
- Monthly spend bar charts

Use the footer shortcuts to move between screens. Press `a` on vehicle, expense, or fuel screens to add records.

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

GitHub Actions run pull request checks for formatting, linting, typing, tests, coverage artifacts, and Docker builds. Releases are created by pushing a version tag in the form `vX.Y.Z`; the tag version must match the version in `pyproject.toml`.

## Roadmap

### v0.1 - Core CLI

Implemented:

- Vehicle management
- Expense logging
- Fuel logging
- Basic summaries
- SQLite backend
- Docker support

### v0.2 - Calculations Engine

Implemented:

- Cost per mile
- UK MPG fuel economy
- Rolling averages
- Category breakdowns
- Monthly and annual summaries

### v0.3 - TUI Interface

Implemented:

- Interactive dashboard
- Vehicle overview
- Expense tables
- Fuel log table
- Cost summaries
- Terminal-based cost graphs

## Licence

Odometer is open source and released under the GNU General Public License v3.0 (GPL-3.0).

See the [LICENSE](LICENSE) file for details.
