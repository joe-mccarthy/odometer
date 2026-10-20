"""Lazy local web launcher."""

from typing import Annotated

import typer


def web(port: Annotated[int, typer.Option(min=1, max=65535)] = 8765) -> None:
    """Start the local browser interface in the foreground."""
    from odometer.web.server import run_server

    try:
        run_server(port)
    except OSError as exception:
        typer.echo(f"Cannot start local server on port {port}: {exception.strerror}", err=True)
        raise typer.Exit(1) from exception
