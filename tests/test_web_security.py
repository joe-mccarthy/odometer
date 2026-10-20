"""Host, browser origin, body limits and packaged file boundaries."""

import pytest
from fastapi.testclient import TestClient

from odometer.web.app import create_app
from odometer.web.security import LocalBoundary

BASE = "http://127.0.0.1:9876"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "security.db", port=9876), base_url=BASE) as current:
        yield current


@pytest.mark.parametrize(
    "host",
    [
        "evil.test:9876",
        "127.0.0.1.evil.test:9876",
        "127.0.0.1",
        "localhost:8765",
        "127.0.0.1:9876@evil.test",
        "[::1]:9876",
    ],
)
@pytest.mark.parametrize("path", ["/api/vehicles", "/", "/static/app.js"])
def test_host_rejection(client, host, path):
    assert client.get(path, headers={"Host": host}).status_code == 403


def test_duplicate_host_and_forwarded_headers(client):
    assert (
        client.get(
            "/api/vehicles", headers=[("Host", "127.0.0.1:9876"), ("Host", "evil.test")]
        ).status_code
        == 403
    )
    for name in ("X-Forwarded-Host", "X-Forwarded-For", "Forwarded"):
        assert client.get("/api/vehicles", headers={name: "evil.test"}).status_code == 403
    assert client.get("/api/vehicles", headers={"Host": "LOCALHOST:9876"}).status_code == 200


@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "https://127.0.0.1:9876",
        "http://127.0.0.1:8765",
        "http://localhost:9876",
        "http://evil.test:9876",
    ],
)
def test_origin_rejection(client, origin):
    assert client.get("/api/vehicles", headers={"Origin": origin}).status_code == 403
    response = client.options(
        "/api/vehicles", headers={"Origin": origin, "Access-Control-Request-Method": "POST"}
    )
    assert response.status_code == 403
    assert not any(name.startswith("access-control-") for name in response.headers)


def test_mutation_headers_and_no_cors(client):
    body = {"registration": "AB12 CDE", "initial_mileage": 0}
    for headers in (
        {},
        {"Origin": BASE},
        {"X-Odometer-Request": "1"},
        {"Origin": BASE, "X-Odometer-Request": "2"},
    ):
        assert client.post("/api/vehicles", json=body, headers=headers).status_code == 403
    assert client.get("/api/vehicles", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    headers = {"Origin": BASE, "X-Odometer-Request": "1"}
    assert client.post("/api/vehicles", content="{}", headers=headers).status_code == 415
    assert client.post("/api/vehicles", json=body, headers=headers).status_code == 201
    assert client.get("/api/vehicles").status_code == 200
    assert (
        client.get(
            "/api/vehicles", headers={"Host": "localhost:9876", "Origin": "http://localhost:9876"}
        ).status_code
        == 200
    )
    assert client.options("/api/vehicles").status_code == 405


def test_body_limits_including_chunked(client):
    headers = {"Origin": BASE, "X-Odometer-Request": "1", "Content-Type": "application/json"}
    for content in (b" " * 65537, iter([b" " * 32768, b" " * 32769])):
        assert client.post("/api/vehicles", content=content, headers=headers).status_code == 413
    assert client.get("/api/vehicles").json() == []


def test_security_headers_and_static_boundary(client):
    for path in (
        "/api/unknown",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/static/../app.py",
        "/static/%2e%2e/app.py",
        "/static/",
    ):
        response = client.get(path)
        assert response.status_code in (404, 405)
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/api/unknown").headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_raw_chunked_and_disconnect():
    async def downstream(scope, receive, send):
        raise AssertionError("Rejected body must not reach application")

    boundary = LocalBoundary(downstream, 9876)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/vehicles",
        "headers": [
            (b"host", b"127.0.0.1:9876"),
            (b"origin", BASE.encode()),
            (b"x-odometer-request", b"1"),
            (b"content-type", b"application/json"),
        ],
    }
    messages = iter(
        [
            {"type": "http.request", "body": b"x" * 40000, "more_body": True},
            {"type": "http.request", "body": b"x" * 40000, "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    await boundary(scope, receive, send)
    assert sent[0]["status"] == 413
    messages = iter([{"type": "http.disconnect"}])
    sent.clear()
    await boundary(scope, receive, send)
    assert sent == []


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_static_assets_from_configured_package_directory(client, tmp_path, monkeypatch):
    import importlib

    module = importlib.import_module("odometer.web.app")
    assets = tmp_path / "package" / "static"
    assets.mkdir(parents=True)
    for name, content in {
        "index.html": "<!doctype html><title>Local</title>",
        "app.js": "'use strict';",
        "styles.css": "body { color: black; }",
    }.items():
        (assets / name).write_text(content)
    monkeypatch.setattr(module, "STATIC", assets)
    unrelated = tmp_path / "cwd"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    with TestClient(module.create_app(tmp_path / "assets.db", port=9876), base_url=BASE) as browser:
        assert browser.get("/").status_code == 200
        assert browser.get("/static/app.js").text == "'use strict';"
        assert browser.get("/static/styles.css").status_code == 200
        assert browser.get("/static/%2e%2e/assets.db").status_code == 404
        assert browser.get("/static/").status_code == 404
        assert browser.get("/api/not-a-route").json()["error"]["code"] == "not_found"
