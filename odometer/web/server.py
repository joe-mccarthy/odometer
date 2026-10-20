"""Foreground IPv4 loopback server."""

import socket

import uvicorn

from odometer.web.app import create_app


def run_server(port: int = 8765) -> None:
    """Bind before bootstrapping so an occupied port fails clearly."""
    if not 1 <= port <= 65535:
        raise ValueError("Port must be 1..65535")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen(128)
        config = uvicorn.Config(
            create_app(port=port),
            host="127.0.0.1",
            port=port,
            proxy_headers=False,
            workers=1,
            reload=False,
            server_header=False,
        )
        print(f"Odometer: http://127.0.0.1:{port}", flush=True)
        uvicorn.Server(config).run(sockets=[listener])
