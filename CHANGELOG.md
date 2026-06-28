# Changelog

## Unreleased

- Initial implementation of Odometer through v0.3.

## v0.3 - TUI Interface

- Added a Textual TUI with dashboard, vehicle overview, vehicle detail, expense, fuel, and summary screens.
- Added terminal bar charts for monthly spend.
- Added simple modal forms for vehicles, expenses, and fuel logs.

## v0.2 - Calculations Engine

- Added running and ownership cost per mile calculations.
- Added UK MPG calculation using imperial gallons and full-to-full fuel logs.
- Added rolling monthly averages, category breakdowns, and monthly/annual summaries.

## v0.1 - Core CLI

- Added vehicle management, expense logging, fuel logging, basic summaries, and SQLite storage.
- Added local database path resolution with `ODOMETER_DB_PATH` override.
- Added Docker support for CLI/TUI use.
