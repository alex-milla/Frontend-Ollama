"""
Inicialización de SQLite y migraciones ligeras.
Todas las operaciones usan parámetros enlazados para evitar SQL injection.
"""
import sqlite3
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def get_db(db_path: str) -> sqlite3.Connection:
    """Devuelve conexión con row_factory y foreign keys activados."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # mejor concurrencia
    conn.execute("PRAGMA busy_timeout = 5000")  # evita SQLITE_BUSY
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    username            TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash       TEXT    NOT NULL,
    role                TEXT    NOT NULL DEFAULT 'user'
                            CHECK(role IN ('admin', 'user')),
    must_change_password INTEGER NOT NULL DEFAULT 1
                            CHECK(must_change_password IN (0, 1)),
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL DEFAULT 'Nueva conversación',
    model       TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
    content         TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

-- Índices útiles
CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conv
    ON messages(conversation_id, created_at ASC);
"""


def init_db(db_path: str) -> None:
    """Crea las tablas si no existen e inserta el usuario admin inicial."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_db(db_path)
    try:
        conn.executescript(_SCHEMA)
        _seed_admin(conn)
        conn.commit()
        log.info("Base de datos inicializada en %s", db_path)
    finally:
        conn.close()


def _seed_admin(conn: sqlite3.Connection) -> None:
    """Inserta admin/admin solo si no existe ningún admin."""
    from werkzeug.security import generate_password_hash

    row = conn.execute(
        "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
    ).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO users (username, password_hash, role, must_change_password)
               VALUES (?, ?, 'admin', 1)""",
            ("admin", generate_password_hash("admin")),
        )
        log.info("Usuario admin creado con contraseña temporal 'admin'")
