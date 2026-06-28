"""Test fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlmodel import Session

from odometer.db.bootstrap import initialise_database
from odometer.db.session import DB_PATH_ENV, get_session


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """Return an isolated SQLite session."""
    database_path = tmp_path / "odometer.db"
    monkeypatch.setenv(DB_PATH_ENV, str(database_path))
    initialise_database()
    with get_session() as db_session:
        yield db_session
