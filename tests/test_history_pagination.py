"""Complete, bounded history traversal and full-history summary regressions."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from odometer.models.enums import ExpenseCategory
from odometer.models.expense import Expense
from odometer.models.fuel import FuelLog
from odometer.services.expense_service import ExpenseService
from odometer.services.fuel_service import FuelService
from odometer.services.summary_service import SummaryService
from odometer.services.vehicle_service import VehicleService
from odometer.web.app import create_app


def seed(session):
    vehicle = VehicleService(session).create_vehicle(
        registration="PAGE 1", initial_mileage=0, fuel_tank_litres=60
    )
    for i in range(1205):
        session.add(
            FuelLog(
                id=f"f{i:05}",
                vehicle_id=vehicle.id,
                date=date(2026, 1, 1),
                odometer_miles=i,
                litres=1,
                total_cost_pence=100,
                price_per_litre_pence=100,
            )
        )
        session.add(
            Expense(
                id=f"e{i:05}",
                vehicle_id=vehicle.id,
                date=date(2026, 1, 1),
                category=ExpenseCategory.SERVICE,
                amount_pence=200,
            )
        )
    session.commit()
    return vehicle.id


def test_service_traversal_and_summary(session):
    identifier = seed(session)
    queries = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(session.get_bind(), "before_cursor_execute", capture)
    try:
        for service, prefix in [
            (FuelService(session).list_fuel_logs, "f"),
            (ExpenseService(session).list_expenses, "e"),
        ]:
            for ascending in (False, True):
                pages = [
                    service(vehicle_identifier=identifier, offset=n, ascending=ascending)
                    for n in range(0, 1205, 50)
                ]
                ids = [row.id for page in pages for row in page]
                assert ids == sorted(
                    [f"{prefix}{i:05}" for i in range(1205)], reverse=not ascending
                )
                assert max(map(len, pages)) == 50
                # Returning to a previous page yields precisely the same order.
                assert [
                    r.id
                    for r in service(vehicle_identifier=identifier, offset=50, ascending=ascending)
                ] == ids[50:100]
        history_queries = [q for q in queries if "FROM fuellog" in q or "FROM expense" in q]
        assert history_queries and all("LIMIT" in q and "OFFSET" in q for q in history_queries)
    finally:
        event.remove(session.get_bind(), "before_cursor_execute", capture)
    assert (
        SummaryService(session).overall_summary(vehicle_identifier=identifier).total_spend_pence
        == 361500
    )
    for service in [FuelService(session).list_fuel_logs, ExpenseService(session).list_expenses]:
        for kwargs in [
            dict(limit=0),
            dict(limit=201),
            dict(offset=-1),
            dict(date_from=date(2026, 2, 1), date_to=date(2026, 1, 1)),
        ]:
            with pytest.raises(ValueError):
                service(vehicle_identifier=identifier, **kwargs)


def test_api_pages_filters_and_bounds(session):
    identifier = seed(session)
    with TestClient(create_app(), base_url="http://127.0.0.1:8765") as client:
        for endpoint, prefix in [("fuel", "f"), ("expenses", "e")]:
            path = f"/api/vehicles/{identifier}/{endpoint}"
            ids = []
            for offset in range(0, 1250, 50):
                response = client.get(path, params=dict(page="true", offset=offset))
                assert response.status_code == 200
                page = response.json()
                assert len(page["items"]) <= 50
                assert page["has_next"] == (offset < 1200)
                ids.extend(row["id"] for row in page["items"])
            assert ids == [f"{prefix}{i:05}" for i in reversed(range(1205))]
            assert len(client.get(path).json()) == 50  # Compatible array response.
            for params in [
                dict(limit=201),
                dict(limit=0),
                dict(offset=-1),
                dict(date_from="2026-02-01", date_to="2026-01-01"),
                dict(date_from="bad"),
            ]:
                assert client.get(path, params=params).status_code == 422
            assert len(client.get(path, params=dict(limit=200)).json()) == 200
            params = dict(page="true", date_from="2026-01-01", date_to="2026-01-01")
            assert len(client.get(path, params=params).json()["items"]) == 50
            params["date_from"] = params["date_to"] = "2026-01-02"
            assert client.get(path, params=params).json()["items"] == []
        path = f"/api/vehicles/{identifier}/expenses"
        assert client.get(path, params=dict(category="MOT", page="true")).json()["items"] == []
        assert (
            len(client.get(path, params=dict(category="SERVICE", date_to="2026-01-01")).json())
            == 50
        )


def test_cli_pages(session):
    from typer.testing import CliRunner

    from odometer.cli.app import app

    seed(session)
    runner = CliRunner()
    for kind, prefix in [("fuel", "f"), ("expense", "e")]:
        result = runner.invoke(app, [kind, "list", "--limit", "5", "--offset", "1200"])
        assert result.exit_code == 0, result.output
        assert prefix + "00004" in result.output
        assert prefix + "00000" in result.output
        assert prefix + "00005" not in result.output
        assert runner.invoke(app, [kind, "list", "--limit", "201"]).exit_code != 0
