"""
Funciones de acceso a datos.
Nunca se construyen queries con f-strings con datos de usuario.
"""
from __future__ import annotations
import sqlite3
from typing import Optional


# ── Usuarios ──────────────────────────────────────────────────────────────────

def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, username, role, must_change_password, created_at FROM users ORDER BY created_at"
    ).fetchall()


def create_user(conn: sqlite3.Connection, username: str, password_hash: str, role: str = "user") -> int:
    cur = conn.execute(
        """INSERT INTO users (username, password_hash, role, must_change_password)
           VALUES (?, ?, ?, 1)""",
        (username, password_hash, role),
    )
    conn.commit()
    return cur.lastrowid


def delete_user(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()


def update_password(conn: sqlite3.Connection, user_id: int, password_hash: str, must_change: bool = False) -> None:
    conn.execute(
        "UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
        (password_hash, 1 if must_change else 0, user_id),
    )
    conn.commit()


# ── Conversaciones ────────────────────────────────────────────────────────────

def list_conversations(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT id, title, model, created_at, updated_at
           FROM conversations WHERE user_id = ?
           ORDER BY updated_at DESC""",
        (user_id,),
    ).fetchall()


def create_conversation(conn: sqlite3.Connection, user_id: int, model: str) -> int:
    cur = conn.execute(
        "INSERT INTO conversations (user_id, model) VALUES (?, ?)",
        (user_id, model),
    )
    conn.commit()
    return cur.lastrowid


def get_conversation(conn: sqlite3.Connection, conv_id: int, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    ).fetchone()


def update_conversation_title(conn: sqlite3.Connection, conv_id: int, title: str) -> None:
    conn.execute(
        """UPDATE conversations SET title = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
           WHERE id = ?""",
        (title, conv_id),
    )
    conn.commit()


def touch_conversation(conn: sqlite3.Connection, conv_id: int) -> None:
    conn.execute(
        "UPDATE conversations SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = ?",
        (conv_id,),
    )
    conn.commit()


def delete_conversation(conn: sqlite3.Connection, conv_id: int, user_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ── Mensajes ──────────────────────────────────────────────────────────────────

def list_messages(conn: sqlite3.Connection, conv_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conv_id,),
    ).fetchall()


def add_message(conn: sqlite3.Connection, conv_id: int, role: str, content: str) -> int:
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conv_id, role, content),
    )
    conn.commit()
    return cur.lastrowid


# ── App Settings ──────────────────────────────────────────────────────────────

def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
