"""Release-review regressions: precision, stale provenance and concurrent history."""

# ruff: noqa: F811
from datetime import timedelta

import pytest
from sqlmodel import Session
from test_reminders import TODAY, observation, status, vehicle
from test_web_api import client, fuel  # noqa: F401, F811
from test_web_api import vehicle as api_vehicle

from odometer.services.reminder_service import ReminderService


@pytest.mark.parametrize(
    "age,delta,expected",
    [(90, 500, "upcoming"), (91, 500, "unknown"), (91, 0, "due"), (91, 1001, "unknown")],
)
def test_stale_near_threshold(session, age, delta, expected):
    v = vehicle(session)
    observation(session, v, miles=13500, when=TODAY - timedelta(days=age))
    svc = ReminderService(session)
    svc.create(
        vehicle_identifier=v.id, title="Service", category="service", due_mileage=13500 + delta
    )
    assert status(svc) == expected


def test_concurrent_completion_blocks_edit(session, monkeypatch):
    v = vehicle(session)
    svc = ReminderService(session)
    row = svc.create(vehicle_identifier=v.id, title="Original", category="mot", due_mileage=14000)
    original_get = svc.get

    def raced_get(identifier):
        active = original_get(identifier)
        with Session(session.get_bind()) as other:
            ReminderService(other).complete(reminder_id=identifier)
        return active

    monkeypatch.setattr(svc, "get", raced_get)
    with pytest.raises(ValueError, match="history"):
        svc.update(reminder_id=row.id, title="Changed", category="service", due_mileage=15000)
    session.expire_all()
    retained = original_get(row.id)
    assert retained.title == "Original"
    assert retained.due_mileage == 14000
    assert retained.completed_at is not None


def test_partial_fill_omission_and_explicit_flags(client):
    v = api_vehicle(client)
    record = fuel(client, v["id"], 120, is_full_tank=False).json()
    body = {k: record[k] for k in ("date", "odometer_miles", "litres", "total_cost_pence")}
    body["notes"] = "corrected"
    url = "/api/fuel/" + record["id"]
    assert client.put(url, json=body).json()["is_full_tank"] is False
    for flag in (True, False):
        assert client.put(url, json={**body, "is_full_tank": flag}).json()["is_full_tank"] is flag


def test_deletion_reports_active_and_completed(client):
    v = api_vehicle(client)
    for title in ("active", "completed"):
        row = client.post(
            f"/api/vehicles/{v['id']}/reminders",
            json={"title": title, "category": "MOT", "due_mileage": 500},
        ).json()
        if title == "completed":
            assert client.post(f"/api/reminders/{row['id']}/complete", json={}).status_code == 200
    result = client.delete("/api/vehicles/" + v["id"]).json()
    assert result["reminder_count"] == 2
    assert client.get("/api/reminders").json() == []


def test_boundary_money_summary(client):
    v = api_vehicle(client)
    maximum = 9223372036854775807
    for _ in range(2):
        response = client.post(
            f"/api/vehicles/{v['id']}/expenses",
            json={"date": "2026-01-01", "category": "MOT", "amount_pence": maximum},
        )
        assert response.status_code == 201
        assert response.json()["amount_pence_exact"] == str(maximum)
    data = client.get("/api/summary?year=2026").json()
    assert data["overall"]["total_spend_pence_exact"] == str(maximum * 2)
    assert data["rolling"]["all_months_average_pence_exact"] == str(maximum * 2)
    assert data["rolling"]["last_3_months_average_pence_exact"] == str(maximum * 2)
