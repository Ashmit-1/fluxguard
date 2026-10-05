"""Turso connection management for the authentication database.

Each operation opens and closes a short-lived remote connection. The
``users`` and ``sessions`` tables are created in Turso on application startup.

Usage::

    from app.auth.database import get_connection, init_auth_db

    init_auth_db()  # called on app startup
    with get_connection() as conn:
        conn.execute("SELECT ...")
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

import turso_serverless

logger = logging.getLogger(__name__)


def _get_turso_credentials() -> tuple[str, str]:
    """Return required Turso credentials or raise a configuration error."""
    database_url = os.getenv("TURSO_DATABASE_URL", "").strip()
    auth_token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
    missing = [
        name
        for name, value in (
            ("TURSO_DATABASE_URL", database_url),
            ("TURSO_AUTH_TOKEN", auth_token),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required Turso configuration: " + ", ".join(missing)
        )
    return database_url, auth_token


@contextmanager
def get_connection() -> Iterator[turso_serverless.Connection]:
    """Open a short-lived connection to the configured Turso database."""
    database_url, auth_token = _get_turso_credentials()
    conn = turso_serverless.connect(database_url, auth_token=auth_token)
    try:
        conn.row_factory = turso_serverless.Row
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            logger.warning("Failed to close Turso connection cleanly.", exc_info=True)


def _cleanup_expired_sessions(conn: turso_serverless.Connection) -> None:
    """Delete expired session rows during startup."""
    cursor = conn.execute(
        "DELETE FROM sessions WHERE expires_at <= datetime('now')"
    )
    conn.commit()
    deleted = cursor.rowcount
    if deleted:
        logger.info("Cleaned up %d expired session(s).", deleted)


def init_auth_db() -> None:
    """Create the auth tables in Turso if they do not already exist.

    Safe to call multiple times — uses ``CREATE TABLE IF NOT EXISTS``.
    Called during application startup.
    """
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                password    TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token       TEXT    NOT NULL UNIQUE,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                expires_at  TEXT    NOT NULL,
                is_active   INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        """)
        conn.commit()
        logger.info("Turso auth database tables initialised.")

        _cleanup_expired_sessions(conn)
