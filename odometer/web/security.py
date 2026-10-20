"""ASGI boundary checks before routing or database access."""

import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'none'; form-action 'self'"
)
MAX_BODY = 64 * 1024


def error(
    status: int, code: str, message: str, fields: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "fields": fields or {}}}, status_code=status
    )


class LocalBoundary:
    def __init__(self, app: ASGIApp, port: int) -> None:
        self.app = app
        self.authorities = {f"127.0.0.1:{port}", f"localhost:{port}"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        response_started = False

        async def secure_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", CSP.encode()),
                ]
                if scope["path"].startswith("/api"):
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        headers: dict[bytes, list[str]] = {}
        for key, value in scope["headers"]:
            headers.setdefault(key.lower(), []).append(value.decode("latin1"))
        hosts = headers.get(b"host", [])
        authority = hosts[0].lower() if len(hosts) == 1 else ""
        rejection = None
        if authority not in self.authorities or any(
            key.startswith(b"x-forwarded-") or key == b"forwarded" for key in headers
        ):
            rejection = error(403, "forbidden_host", "Invalid local host")
        origins = headers.get(b"origin", [])
        origin_ok = origins == [f"http://{authority}"]
        if rejection is None and (origins and not origin_ok):
            rejection = error(403, "forbidden_origin", "Origin must match the local server")
        if rejection is None and "cross-site" in headers.get(b"sec-fetch-site", []):
            rejection = error(403, "forbidden_origin", "Cross-site requests are forbidden")
        mutation = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if rejection is None and mutation and not origin_ok:
            rejection = error(403, "forbidden_origin", "A matching Origin is required")
        if rejection is None and mutation and headers.get(b"x-odometer-request") != ["1"]:
            rejection = error(403, "forbidden_request", "X-Odometer-Request: 1 is required")
        if rejection is None and scope["method"] in {"POST", "PATCH"}:
            media = headers.get(b"content-type", [])
            if len(media) != 1 or media[0].split(";", 1)[0].strip().lower() != "application/json":
                rejection = error(415, "unsupported_media_type", "Use application/json")
        if rejection is not None:
            return await rejection(scope, receive, secure_send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY:
                return await error(413, "payload_too_large", "Request exceeds 64 KiB")(
                    scope, receive, secure_send
                )
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        try:
            await self.app(scope, replay, secure_send)
        except Exception:
            logging.getLogger(__name__).exception("Unexpected HTTP failure")
            if response_started:
                raise
            await error(500, "internal_error", "An internal error occurred")(
                scope, receive, secure_send
            )
