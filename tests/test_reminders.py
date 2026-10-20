"""Reminder boundaries, atomic history, provenance and interface parity."""

import sqlite3
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from typer.testing import CliRunner

from odometer.cli.app import app
from odometer.db.session import DB_PATH_ENV
from odometer.models import Expense, ExpenseCategory, FuelLog, Reminder, VehicleStatus
from odometer.services.reminder_service import ReminderService
from odometer.services.vehicle_service import VehicleService
from odometer.web.app import create_app

TODAY = date(2026, 10, 20)


def vehicle(session):
    return VehicleService(session).create_vehicle(registration="AB12 CDE", initial_mileage=10000)


def observation(session, v, miles=11000, when=TODAY, id_="z"):
    row = Expense(
        id=id_,
        vehicle_id=v.id,
        date=when,
        category=ExpenseCategory.MOT,
        amount_pence=5000,
        odometer_miles=miles,
    )
    session.add(row)
    session.commit()
    return row


def status(service):
    return service.list(today=TODAY)[0]["status"]


@pytest.mark.parametrize(
    "days,delta,expected",
    [
        (0, 2000, "due"),
        (-1, None, "due"),
        (30, 1001, "upcoming"),
        (31, 1000, "upcoming"),
        (31, 1001, "later"),
        (None, 0, "due"),
        (100, -1, "due"),
        (None, 1001, "later"),
        (None, 1000, "upcoming"),
    ],
)
def test_boundaries(session, days, delta, expected):
    v = vehicle(session)
    observation(session, v)
    svc = ReminderService(session)
    svc.create(
        vehicle_identifier=v.id,
        title="Service",
        category="service",
        due_date=TODAY + timedelta(days=days) if days is not None else None,
        due_mileage=11000 + delta if delta is not None else None,
    )
    assert status(svc) == expected


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"title": " "},
        {"category": "wrong"},
        {"due_mileage": -1},
        {"due_mileage": True},
        {"due_mileage": 1.5},
        {"due_mileage": 9007199254740992},
        {"due_date": "2026-10-20"},
    ],
)
def test_validation_no_write(session, fields):
    v = vehicle(session)
    svc = ReminderService(session)
    data = dict(vehicle_identifier=v.id, title="Service", category="SERVICE", due_date=TODAY)
    if not fields:
        data.pop("due_date")
    data.update(fields)
    with pytest.raises(ValueError):
        svc.create(**data)
    assert not session.exec(select(Reminder)).all()


def test_missing_stale_and_latest_provenance(session):
    v = vehicle(session)
    svc = ReminderService(session)
    r = svc.create(vehicle_identifier=v.id, title="MOT", category="MOT", due_mileage=9000)
    assert status(svc) == "unknown"  # baseline cannot prove reached
    observation(session, v, miles=12000, when=TODAY - timedelta(days=91), id_="a")
    assert status(svc) == "due"  # stale reached threshold still due
    svc.update(reminder_id=r.id, title="MOT", category="MOT", due_mileage=14000)
    assert status(svc) == "unknown"
    observation(session, v, miles=12000, when=TODAY - timedelta(days=90), id_="b")
    assert status(svc) == "later"
    session.add(
        FuelLog(
            id="c",
            vehicle_id=v.id,
            date=TODAY - timedelta(days=90),
            odometer_miles=13000,
            litres=10,
            total_cost_pence=1500,
        )
    )
    session.commit()
    row = svc.list(today=TODAY)[0]
    assert row["status"] == "upcoming" and row["reading"]["source"] == "fuel"
    assert row["reading"]["date"] == TODAY - timedelta(days=90)
    observation(session, v, miles=11000, when=TODAY, id_="d")
    assert svc.list(today=TODAY)[0]["reading"]["miles"] == 11000  # latest, not maximum
    svc.update(reminder_id=r.id, title="MOT", category="MOT", due_date=TODAY, due_mileage=None)
    assert status(svc) == "due"


def test_completion_atomic_history_lifecycle_delete(session):
    v = vehicle(session)
    svc = ReminderService(session)
    r = svc.create(vehicle_identifier=v.id, title="MOT", category="MOT", due_date=TODAY)
    with pytest.raises(ValueError):
        svc.complete(reminder_id=r.id, next_due_mileage=-1)
    assert svc.get(r.id).completed_at is None
    with patch.object(session, "commit", side_effect=RuntimeError("fail")):
        with pytest.raises(RuntimeError):
            svc.complete(reminder_id=r.id, next_due_date=TODAY)
    assert svc.get(r.id).completed_at is None
    assert len(session.exec(select(Reminder)).all()) == 1
    result = svc.complete(reminder_id=r.id, next_due_date=TODAY + timedelta(days=365))
    nxt = result["next"]
    assert nxt.previous_id == r.id and nxt.title == r.title
    assert result["completed"].completed_at is not None
    with pytest.raises(ValueError):
        svc.complete(reminder_id=r.id)
    with pytest.raises(ValueError):
        svc.update(reminder_id=r.id, title="x", category="MOT", due_date=TODAY)
    svc.complete(reminder_id=nxt.id)
    assert all(i["status"] == "completed" for i in svc.list(today=TODAY))
    VehicleService(session).mark_vehicle_sold(v.id)
    assert svc.list() == [] and len(svc.list(include_inactive=True)) == 2
    v.status = VehicleStatus.ACTIVE
    session.add(v)
    session.commit()
    assert len(svc.list()) == 2
    VehicleService(session).archive_vehicle(v.id)
    assert svc.list() == []
    svc.delete(r.id)
    VehicleService(session).delete_vehicle(v.id)
    assert not session.exec(select(Reminder)).all()


def test_api_crud_security_backup(tmp_path, monkeypatch):
    path = tmp_path / "source.db"
    monkeypatch.setenv(DB_PATH_ENV, str(path))
    client = TestClient(create_app(path), base_url="http://127.0.0.1:8765")
    headers = {"X-Odometer-Request": "1", "Origin": "http://127.0.0.1:8765"}
    v = client.post(
        "/api/vehicles", json={"registration": "AB12 CDE", "initial_mileage": 0}, headers=headers
    ).json()
    endpoint = f"/api/vehicles/{v['id']}/reminders"
    body = {"title": "MOT", "category": "MOT", "due_date": "2026-10-20", "due_mileage": 123}
    assert client.post(endpoint, json=body).status_code == 403
    for bad in [
        {"due_date": "20261020"},
        {"due_mileage": True},
        {"title": " "},
        {"category": "bad"},
        {"extra": 1},
    ]:
        assert client.post(endpoint, json=body | bad, headers=headers).status_code == 422
    r = client.post(endpoint, json=body, headers=headers)
    assert r.status_code == 201
    rid = r.json()["id"]
    url = "/api/reminders/" + rid
    edited = client.put(
        url, json=body | {"title": "Annual MOT", "due_mileage": None}, headers=headers
    ).json()
    assert edited["id"] == rid and edited["vehicle_id"] == v["id"]
    assert (
        client.post(url + "/complete", json={"next_due_mileage": 200}, headers=headers).status_code
        == 200
    )
    rows = client.get("/api/reminders").json()
    assert len(rows) == 2
    backup = client.get("/api/downloads/backup")
    assert backup.status_code == 200
    dest = tmp_path / "backup.db"
    dest.write_bytes(backup.content)
    with sqlite3.connect(dest) as db:
        assert db.execute("select count(*) from reminder").fetchone()[0] == 2
        assert (
            db.execute("select count(*) from reminder where previous_id=?", (rid,)).fetchone()[0]
            == 1
        )
    assert client.get("/api/reminders", headers={"Host": "evil.test"}).status_code == 403
    assert client.delete(url, headers=headers).status_code == 200
    assert client.delete(url, headers=headers).status_code == 404


def test_cli_workflow(session):
    v = vehicle(session)
    runner = CliRunner()

    def invoke(args, input=None):
        result = runner.invoke(app, ["reminder", *args], input=input)
        assert result.exit_code == 0, result.output
        return result.output

    assert (
        runner.invoke(
            app, ["reminder", "add", "--vehicle", v.id, "--title", "MOT", "--category", "MOT"]
        ).exit_code
        == 1
    )
    invoke(
        [
            "add",
            "--vehicle",
            v.id,
            "--title",
            "MOT",
            "--category",
            "MOT",
            "--due-date",
            "2026-10-20",
        ]
    )
    session.expire_all()
    r = session.exec(select(Reminder)).one()
    invoke(["edit", r.id, "--title", "Renewal", "--category", "TAX", "--due-mileage", "12000"])
    out = invoke(["list"])
    assert "Renewal" in out and "unknown" in out and "baseline" in out
    invoke(["complete", r.id, "--next-due-mileage", "15000"])
    assert "completed" in invoke(["list"])
    invoke(["delete", r.id], input="n\n")
    session.expire_all()
    assert session.get(Reminder, r.id) is not None
    invoke(["delete", r.id], input="y\n")
    assert "1,000" in invoke(["--help"])


def test_completion_rejects_stale_session_retry(session):
    """A second request holding a cached active row cannot schedule another next occurrence."""
    v = vehicle(session)
    svc = ReminderService(session)
    row = svc.create(vehicle_identifier=v.id, title="MOT", category="MOT", due_date=TODAY)
    with Session(session.get_bind(), expire_on_commit=False) as other:
        second = ReminderService(other)
        cached = second.get(row.id)
        assert cached.completed_at is None
        svc.complete(reminder_id=row.id, next_due_mileage=20000)
        with pytest.raises(ValueError, match="already completed"):
            second.complete(reminder_id=row.id, next_due_mileage=30000)
    session.expire_all()
    assert len(session.exec(select(Reminder)).all()) == 2
