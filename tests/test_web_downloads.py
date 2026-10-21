"""Whole-database download compatibility and containment."""

import csv
import importlib
import io
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from odometer.web.app import create_app

BASE = "http://127.0.0.1:8765"


@pytest.fixture
def downloads(tmp_path):
    source = tmp_path / "source.db"
    with TestClient(create_app(source), base_url=BASE) as client:
        yield client, source


def test_empty_exports_and_safe_headers(downloads):
    client, _ = downloads
    for kind in ("json", "vehicles", "fuel", "expenses", "backup"):
        response = client.get(f"/api/downloads/{kind}")
        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith(
            f'attachment; filename="odometer-{kind}-'
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        if kind == "json":
            assert response.json() == {
                "format_version": 1,
                "vehicles": [],
                "fuel": [],
                "expenses": [],
            }
        elif kind != "backup":
            assert len(list(csv.reader(io.StringIO(response.text)))) == 1
    assert client.get("/api/downloads/unknown").status_code == 404
    assert client.get("/api/downloads/json?path=/tmp/private").status_code == 422


def test_snapshot_includes_inactive_wal_and_extra_tables(downloads, tmp_path):
    client, source = downloads
    headers = {"Origin": BASE, "X-Odometer-Request": "1"}
    created = client.post(
        "/api/vehicles",
        headers=headers,
        json={"registration": "PRIVATE", "initial_mileage": 42, "purchase_price_pence": 12345},
    ).json()
    client.patch(f"/api/vehicles/{created['id']}", headers=headers, json={"status": "SOLD"})
    # Keep a writer open: committed WAL content must be in the standalone backup.
    with sqlite3.connect(source) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("CREATE TABLE extension_state (id TEXT PRIMARY KEY, title TEXT)")
        writer.execute("INSERT INTO extension_state VALUES ('r1', 'Renew insurance')")
        writer.commit()
        exported = client.get("/api/downloads/json").json()
        assert set(exported) == {"format_version", "vehicles", "fuel", "expenses"}
        assert exported["vehicles"][0]["status"] == "SOLD"
        assert exported["vehicles"][0]["purchase_price_pence"] == 12345
        csv_rows = list(csv.DictReader(io.StringIO(client.get("/api/downloads/vehicles").text)))
        assert csv_rows[0]["id"] == created["id"]
        backup = tmp_path / "download.sqlite3"
        backup.write_bytes(client.get("/api/downloads/backup").content)
        with sqlite3.connect(backup) as restored:
            assert restored.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert restored.execute("SELECT title FROM extension_state").fetchone() == (
                "Renew insurance",
            )
            assert restored.execute("SELECT id FROM vehicle").fetchone() == (created["id"],)


def test_boundary_and_failure_cleanup(downloads, tmp_path, monkeypatch):
    client, _ = downloads
    for kind in ("json", "backup"):
        assert (
            client.get(
                f"/api/downloads/{kind}", headers={"Origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert (
            client.get(f"/api/downloads/{kind}", headers={"Host": "evil.test"}).status_code == 403
        )
        assert (
            client.get(
                f"/api/downloads/{kind}", headers={"Sec-Fetch-Site": "cross-site"}
            ).status_code
            == 403
        )
    module = importlib.import_module("odometer.web.app")
    destinations = []

    def fail(source, destination, dataset):
        destinations.append(Path(destination))
        destination.write_text("partial private data")
        raise ValueError("private filesystem path")

    monkeypatch.setattr(module, "export_data", fail)
    # The boundary emits a generic error, without a private path or partial data.
    with TestClient(client.app, base_url=BASE, raise_server_exceptions=False) as safe:
        response = safe.get("/api/downloads/json")
    assert response.status_code == 500
    assert "private" not in response.text
    assert destinations and not destinations[0].parent.exists()
