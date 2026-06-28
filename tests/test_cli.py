"""CLI tests."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from odometer.cli.app import app
from odometer.db.session import DB_PATH_ENV
from odometer.tui.app import OdometerTUI

runner = CliRunner()


def test_help_works() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Track the true cost" in result.output


def test_cli_core_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "odometer.db"
    monkeypatch.setenv(DB_PATH_ENV, str(database_path))

    assert runner.invoke(app, ["init"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "vehicle",
                "add",
                "--registration",
                "AB12 CDE",
                "--make",
                "Ford",
                "--model",
                "Kuga",
                "--year",
                "2019",
                "--initial-mileage",
                "42000",
                "--fuel-tank-litres",
                "55",
                "--purchase-price",
                "12500",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["vehicle", "list"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "expense",
                "add",
                "--vehicle",
                "AB12CDE",
                "--category",
                "service",
                "--amount",
                "249.99",
                "--mileage",
                "43000",
                "--description",
                "Annual service",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["expense", "list"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "fuel",
                "add",
                "--vehicle",
                "AB12CDE",
                "--litres",
                "45.2",
                "--amount",
                "68.50",
                "--mileage",
                "43420",
                "--station",
                "Tesco",
                "--full",
            ],
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["fuel", "list"]).exit_code == 0
    assert runner.invoke(app, ["summary", "--vehicle", "AB12CDE"]).exit_code == 0
    assert runner.invoke(app, ["calc", "mpg", "--vehicle", "AB12CDE"]).exit_code == 0


def test_tui_instantiates() -> None:
    tui = OdometerTUI()

    assert tui is not None
