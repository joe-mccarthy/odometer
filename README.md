# odometer

![Python](https://img.shields.io/badge/python-3.12+-blue?style=flat-square)
![License](https://img.shields.io/github/license/joe-mccarthy/odometer?style=flat-square)
![Issues](https://img.shields.io/github/issues/joe-mccarthy/odometer?style=flat-square)
![Last Commit](https://img.shields.io/github/last-commit/joe-mccarthy/odometer?style=flat-square)

**odometer** is a local-first CLI application for tracking the true cost of owning a vehicle.

It helps you answer a simple question:

> What does this car actually cost me?

Unlike basic fuel trackers, odometer records every ownership expense — fuel, servicing, insurance, tax, repairs, finance — and calculates meaningful metrics like cost per mile and total cost of ownership.

## Philosophy

odometer is designed to be:

- Local-first
- Privacy respecting
- Multi-vehicle
- CLI-first
- Docker-friendly
- Extensible (TUI and web UI planned)

No cloud. No subscriptions. Your data stays with you.

## Features (Planned)

- Track multiple vehicles by registration
- Record all ownership expenses
- Fuel logging with mileage tracking
- Cost per mile calculations
- Monthly and annual cost summaries
- Expense breakdown by category
- SQLite storage (PostgreSQL optional later)
- Docker support

## Roadmap

### v0.1 – Core CLI
- Vehicle management
- Expense logging
- Basic summaries
- SQLite backend
- Docker support

### v0.2 – Calculations Engine
- Cost per mile
- Fuel economy (MPG)
- Rolling averages
- Category breakdowns

### v0.3 – TUI Interface
- Interactive dashboard
- Expense tables
- Cost graphs (terminal-based)

### v1.0 – Web Interface
- API layer
- Self-hosted web dashboard
- Multi-user support (optional)

## License

odometer is open source and released under the GNU General Public License v3.0 (GPL-3.0).

See the [LICENSE](LICENSE) file for details.
