"""HTTP contract and service interoperability against disposable SQLite databases."""

import importlib
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner

from odometer.cli.app import app as cli
from odometer.services.vehicle_service import VehicleService
from odometer.web.app import create_app

BASE = "http://127.0.0.1:8765"
HEADERS = {"Origin": BASE, "X-Odometer-Request": "1"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ODOMETER_DB_PATH", str(tmp_path / "http.db"))
    with TestClient(create_app(), base_url=BASE) as current:
        current.headers.update(HEADERS)
        yield current


def vehicle(client, **kwargs):
    response = client.post(
        "/api/vehicles",
        json={"registration": "AB12 CDE", "initial_mileage": 100, "fuel_tank_litres": 60, **kwargs},
    )
    assert response.status_code == 201, response.text
    return response.json()


def fuel(client, identifier, mileage, **kwargs):
    return client.post(
        f"/api/vehicles/{identifier}/fuel",
        json={
            "date": "2026-01-01",
            "odometer_miles": mileage,
            "litres": 30,
            "total_cost_pence": 4500,
            **kwargs,
        },
    )


def test_vehicle_lifecycle_and_cli(client):
    first = vehicle(client, purchase_price_pence=123456)
    identifier = first["id"]
    assert first["created_at"].endswith("Z")
    assert first["updated_at"].endswith("Z")
    assert first["normalised_registration"] == "AB12CDE"
    assert first["purchase_price_pence"] == 123456
    assert client.get(f"/api/vehicles/{identifier}").json() == first
    assert (
        client.post(
            "/api/vehicles", json={"registration": "ab12cde", "initial_mileage": 0}
        ).status_code
        == 409
    )
    assert (
        client.patch(f"/api/vehicles/{identifier}", json={"fuel_tank_litres": 70}).json()[
            "fuel_tank_litres"
        ]
        == 70
    )
    for status in ("SOLD", "ARCHIVED"):
        assert (
            client.patch(f"/api/vehicles/{identifier}", json={"status": status}).json()["status"]
            == status
        )
    assert client.get("/api/vehicles").json() == []
    assert len(client.get("/api/vehicles?include_inactive=true").json()) == 1
    assert fuel(client, identifier, 100).status_code == 201  # historical records allowed
    response = client.post(
        f"/api/vehicles/{identifier}/expenses",
        json={"date": "2026-01-02", "category": "SERVICE", "amount_pence": 101},
    )
    assert response.status_code == 201
    result = CliRunner().invoke(cli, ["vehicle", "show", identifier])
    assert result.exit_code == 0, result.output
    assert "AB12 CDE" in result.output
    deleted = client.delete(f"/api/vehicles/{identifier}").json()
    assert deleted == {
        "vehicle_id": identifier,
        "registration": "AB12 CDE",
        "expense_count": 1,
        "fuel_log_count": 1,
    }
    assert client.get(f"/api/vehicles/{identifier}").status_code == 404


def test_fuel_expense_summary_and_deletion(client):
    identifier = vehicle(client)["id"]
    assert client.get(f"/api/summary?vehicle_id={identifier}").json()["mpg"] is None
    first = fuel(client, identifier, 100).json()
    partial = fuel(client, identifier, 200, is_full_tank=False, litres=15).json()
    last = fuel(client, identifier, 400, litres=50).json()
    assert fuel(client, identifier, 399).status_code == 422
    assert fuel(client, identifier, 500, litres=80, fuel_tank_litres=65).status_code == 422
    assert client.get(f"/api/vehicles/{identifier}").json()["fuel_tank_litres"] == 60
    expense_path = f"/api/vehicles/{identifier}/expenses"
    expense = client.post(
        expense_path,
        json={
            "date": "2026-01-02",
            "category": "SERVICE",
            "amount_pence": 10001,
            "odometer_miles": 400,
        },
    ).json()
    client.post(
        expense_path, json={"date": "2026-01-02", "category": "FUEL", "amount_pence": 99999}
    )
    summary = client.get(f"/api/summary?vehicle_id={identifier}&year=2026").json()
    assert set(summary) == {"overall", "monthly", "annual", "categories", "rolling", "mpg"}
    assert summary["overall"]["total_spend_pence"] == 23501
    assert summary["mpg"]["average_mpg"] == pytest.approx(300 / (65 / 4.54609))
    assert summary["mpg"]["segment_count"] == 1
    assert len(summary["monthly"]) == 12
    assert client.get("/api/summary").json()["mpg"] is None
    assert client.get(f"{expense_path}?category=SERVICE").json() == [expense]
    assert client.get(f"/api/vehicles/{identifier}/fuel?ascending=true&limit=1").json() == [first]
    assert client.get(f"/api/vehicles/{identifier}/fuel?date_from=2026-02-01").json() == []
    assert client.delete(f"/api/expenses/{expense['id']}").json() == expense
    for log in (first, partial, last):
        assert client.delete(f"/api/fuel/{log['id']}").json() == log
    assert client.get(f"/api/summary?vehicle_id={identifier}").json()["mpg"] is None


@pytest.mark.parametrize(
    "values",
    [
        {"initial_mileage": True},
        {"initial_mileage": "100"},
        {"initial_mileage": 1.5},
        {"initial_mileage": -1},
        {"initial_mileage": 9007199254740992},
        {"registration": " "},
        {"registration": 123},
        {"year": True},
        {"year": 0},
        {"fuel_tank_litres": "50"},
        {"fuel_tank_litres": True},
        {"fuel_tank_litres": 0},
        {"purchase_date": "2026-02-30"},
        {"purchase_date": 0},
        {"purchase_date": "2026-01-01T00:00:00"},
        {"unknown": 1},
        {"purchase_price_pence": 0.5},
        {"purchase_price_pence": None, "registration": None},
    ],
)
def test_strict_vehicle_input(client, values):
    response = client.post(
        "/api/vehicles", json={"registration": "AB12 CDE", "initial_mileage": 0, **values}
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"]
    assert client.get("/api/vehicles").json() == []


@pytest.mark.parametrize(
    "body", [{}, {"status": "ACTIVE"}, {"status": None}, {"status": "SOLD", "fuel_tank_litres": 60}]
)
def test_patch_validation(client, body):
    identifier = vehicle(client)["id"]
    assert client.patch(f"/api/vehicles/{identifier}", json=body).status_code == 422


@pytest.mark.parametrize("suffix", ["include_inactive=1", "include_inactive=TRUE"])
def test_query_boolean(client, suffix):
    assert client.get(f"/api/vehicles?{suffix}").status_code == 422


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=1001",
        "limit=1.5",
        "ascending=1",
        "date_from=2026-02-30",
        "date_from=20260101",
        "date_from=2026-02-01&date_to=2026-01-01",
    ],
)
def test_list_validation(client, query):
    identifier = vehicle(client)["id"]
    for resource in ("fuel", "expenses"):
        assert client.get(f"/api/vehicles/{identifier}/{resource}?{query}").status_code == 422


@pytest.mark.parametrize(
    "query", ["year=0", "year=9999", "year=1.5", "year=true", "include_inactive=1"]
)
def test_summary_validation(client, query):
    assert client.get(f"/api/summary?{query}").status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/vehicles/missing",
        "/api/vehicles/missing/fuel",
        "/api/vehicles/missing/expenses",
        "/api/unknown",
        "/api/summary?vehicle_id=missing",
    ],
)
def test_missing_reads(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "path", ["/api/vehicles/missing", "/api/fuel/missing", "/api/expenses/missing"]
)
def test_missing_deletes(client, path):
    assert client.delete(path).status_code == 404


def test_error_mapping_and_safe_diagnostics(client, monkeypatch):
    response = client.post(
        "/api/vehicles", content="{", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_json"
    assert client.put("/api/vehicles", json={}).status_code == 405
    for exception, status, code in [
        (OperationalError("secret SQL", {}, Exception("database is locked")), 503, "database_busy"),
        (OperationalError("secret SQL", {}, Exception("disk secret")), 500, "internal_error"),
        (ValueError("secret path"), 500, "internal_error"),
    ]:

        def fail(*args, failure=exception, **kwargs):
            raise failure

        monkeypatch.setattr(VehicleService, "list_vehicles", fail)
        response = client.get("/api/vehicles")
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert "secret" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert "content-security-policy" in response.headers


def test_lazy_cli_and_port_validation():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import odometer.cli.app; "
            "assert 'odometer.web.server' not in sys.modules; "
            "assert 'fastapi' not in sys.modules",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert CliRunner().invoke(cli, ["web", "--port", "0"]).exit_code == 2
    assert CliRunner().invoke(cli, ["web", "--port", "65536"]).exit_code == 2


def test_cli_launch_and_occupied_port(monkeypatch):
    import socket

    from odometer.web import server

    seen = []
    monkeypatch.setattr(server, "run_server", lambda port: seen.append(port))
    assert CliRunner().invoke(cli, ["web", "--port", "9876"]).exit_code == 0
    assert seen == [9876]

    def fail(port):
        raise OSError(98, "Address already in use")

    monkeypatch.setattr(server, "run_server", fail)
    assert CliRunner().invoke(cli, ["web"]).exit_code == 1
    importlib.reload(server)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(OSError):
            server.run_server(listener.getsockname()[1])
    with pytest.raises(ValueError):
        server.run_server(0)
    with pytest.raises(ValueError):
        create_app(port=65536)


def test_fuel_expense_transport_and_business_errors(client):
    identifier = vehicle(client, fuel_tank_litres=None)["id"]
    assert fuel(client, identifier, 100).status_code == 422
    assert fuel(client, identifier, 100, fuel_tank_litres=60).status_code == 201
    assert client.get(f"/api/vehicles/{identifier}").json()["fuel_tank_litres"] == 60
    for changes in (
        {"is_full_tank": "false"},
        {"litres": True},
        {"litres": "10"},
        {"total_cost_pence": 1.5},
        {"odometer_miles": True},
        {"date": "2026-02-30"},
        {"notes": 1},
        {"price_per_litre_pence": 0},
    ):
        assert fuel(client, identifier, 200, **changes).status_code == 422
    response = client.post(
        f"/api/vehicles/{identifier}/fuel",
        content=('{"date":"2026-01-01","odometer_miles":200,"litres":NaN,"total_cost_pence":1}'),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    path = f"/api/vehicles/{identifier}/expenses"
    for changes in (
        {"category": "unknown"},
        {"amount_pence": True},
        {"amount_pence": "100"},
        {"amount_pence": 0},
        {"amount_pence": 1.5},
        {"odometer_miles": 99},
        {"date": None},
        {"description": 5},
    ):
        assert (
            client.post(
                path,
                json={"date": "2026-01-01", "category": "SERVICE", "amount_pence": 100, **changes},
            ).status_code
            == 422
        )
    assert client.get(f"{path}?category=unknown").status_code == 422


def test_service_validation_scope(client, monkeypatch):
    def bad_create(*args, **kwargs):
        raise ValueError("Expected service validation")

    monkeypatch.setattr(VehicleService, "create_vehicle", bad_create)
    response = client.post("/api/vehicles", json={"registration": "AB12 CDE", "initial_mileage": 0})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Expected service validation"
