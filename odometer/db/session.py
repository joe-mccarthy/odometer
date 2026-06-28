"""Database session helpers."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from platformdirs import PlatformDirs
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

APP_NAME = "odometer"
DB_FILENAME = "odometer.db"
DB_PATH_ENV = "ODOMETER_DB_PATH"


def get_app_data_dir() -> Path:
    """Return the OS-appropriate local application data directory."""
    return PlatformDirs(APP_NAME, appauthor=False).user_data_path


def get_database_path() -> Path:
    """Return the configured SQLite database path."""
    configured = os.environ.get(DB_PATH_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return get_app_data_dir() / DB_FILENAME


def ensure_database_parent(database_path: Path | None = None) -> Path:
    """Ensure the database parent directory exists and return the database path."""
    path = database_path or get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_engine(database_path: Path | None = None) -> Engine:
    """Create a SQLModel engine for the configured SQLite database."""
    path = ensure_database_parent(database_path)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


@contextmanager
def get_session(database_path: Path | None = None) -> Iterator[Session]:
    """Yield a database session."""
    engine = get_engine(database_path)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
