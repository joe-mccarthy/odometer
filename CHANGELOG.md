# Changelog

## 0.2.0 - 2026-10-20

GitHub-only testing release; no PyPI publication.

- Added a local browser dashboard and service-backed API for vehicles, expenses,
  fuel, summaries, tank updates, sold/archive status and confirmed deletion.
- Added JSON and CSV exports and consistent online SQLite backups via the CLI.
- Added loopback-only serving and host/origin validation for browser mutations.
- Corrected calculation boundary cases and marketing text contrast.
- Updated startup, backup/restore, architecture and release documentation.
- Aligned package and runtime version metadata to 0.2.0.

Known limits: single-user local use; browser lists cap at 1,000 rows; exports and
backups require CLI commands; no import, general editing or reactivation.
Chromium acceptance passed; Firefox/WebKit, native devices, screen readers and
large datasets remain unverified. Docker supports CLI/TUI usage.

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
