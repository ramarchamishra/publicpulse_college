import sqlite3
import os
from contextvars import ContextVar
from pathlib import Path


DATABASE_PATH = Path(__file__).parent / "publicpulse.db"
database_path = ContextVar("publicpulse_database", default=None)


def get_connection():
    path = database_path.get() or os.getenv("PUBLICPULSE_DATABASE") or DATABASE_PATH
    path = Path(path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection
