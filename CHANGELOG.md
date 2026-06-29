# Changelog

## 0.1.0 - 2026-06-29

Initial GitHub-only testing release. This release publishes build artifacts and
checksums through GitHub Releases; PyPI publishing is not enabled yet.

- Initial implementation of Odometer.
- Added vehicle management, expense logging, fuel logging, summaries, and SQLite storage.
- Added running and ownership cost per mile calculations.
- Added UK MPG calculation using imperial gallons and full-to-full fuel logs.
- Added rolling monthly averages, category breakdowns, and monthly or annual summaries.
- Added Docker and Docker Compose support for CLI/TUI use.
- Added a Textual TUI with dashboard, vehicle overview, vehicle detail, expense,
  fuel, and summary screens.
- Added modal forms for vehicles, expenses, and fuel logs.
- Added a shared TUI vehicle context selector for dashboard, expenses, fuel logs, and summaries.
- Added registration columns and explicit fitted column sizing to TUI data tables.
- Added confirmed deletion for vehicles, expenses, and fuel logs.
- Added monthly mileage charts alongside monthly spend charts in the TUI.
