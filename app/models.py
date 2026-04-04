"""
Funciones de acceso a datos.
Nunca se construyen queries con f-strings con datos de usuario.
"""
from __future__ import annotations
import sqlite3
from typing import Optional


# ── Usuarios ──────────────────────────────────────────────────────────────────

def get_user_by_username(conn, username):
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

def get_user_by_id(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def list_users(conn):
    return conn.execute("SELECT id, username, role, must_change_password, created_at FROM users ORDER BY created_at").fetchall()

def create_user(conn, username, password_hash, role="user"):
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, role, must_change_password) VALUES (?, ?, ?, 1)",
        (username, password_hash, role),
    )
    conn.commit()
    return cur.lastrowid

def delete_user(conn, user_id):
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()

def update_password(conn, user_id, password_hash, must_change=False):
    conn.execute(
        "UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
        (password_hash, 1 if must_change else 0, user_id),
    )
    conn.commit()


# ── Conversaciones ────────────────────────────────────────────────────────────

def list_conversations(conn, user_id):
    return conn.execute(
        """SELECT id, title, model, project_id, created_at, updated_at
           FROM conversations WHERE user_id = ?
           ORDER BY updated_at DESC""",
        (user_id,),
    ).fetchall()

def create_conversation(conn, user_id, model, project_id=None):
    cur = conn.execute(
        "INSERT INTO conversations (user_id, model, project_id) VALUES (?, ?, ?)",
        (user_id, model, project_id),
    )
    conn.commit()
    return cur.lastrowid

def get_conversation(conn, conv_id, user_id):
    return conn.execute(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    ).fetchone()

def update_conversation_title(conn, conv_id, title):
    conn.execute(
        "UPDATE conversations SET title=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
        (title, conv_id),
    )
    conn.commit()

def touch_conversation(conn, conv_id):
    conn.execute(
        "UPDATE conversations SET updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
        (conv_id,),
    )
    conn.commit()

def delete_conversation(conn, conv_id, user_id):
    cur = conn.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conv_id, user_id))
    conn.commit()
    return cur.rowcount > 0


# ── Mensajes ──────────────────────────────────────────────────────────────────

def list_messages(conn, conv_id):
    return conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
        (conv_id,),
    ).fetchall()

def add_message(conn, conv_id, role, content):
    cur = conn.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
        (conv_id, role, content),
    )
    conn.commit()
    return cur.lastrowid


# ── App Settings ──────────────────────────────────────────────────────────────

def get_setting(conn, key, default=""):
    row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO app_settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


# ── Proyectos ─────────────────────────────────────────────────────────────────

def list_projects(conn, user_id):
    return conn.execute(
        "SELECT * FROM projects WHERE user_id=? ORDER BY updated_at DESC",
        (user_id,)
    ).fetchall()

def create_project(conn, user_id, name, description=""):
    cur = conn.execute(
        "INSERT INTO projects (user_id, name, description) VALUES (?,?,?)",
        (user_id, name, description)
    )
    conn.commit()
    return cur.lastrowid

def get_project(conn, project_id, user_id):
    return conn.execute(
        "SELECT * FROM projects WHERE id=? AND user_id=?",
        (project_id, user_id)
    ).fetchone()

def update_project(conn, project_id, user_id, name, description):
    conn.execute(
        "UPDATE projects SET name=?, description=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND user_id=?",
        (name, description, project_id, user_id)
    )
    conn.commit()

def delete_project(conn, project_id, user_id):
    cur = conn.execute("DELETE FROM projects WHERE id=? AND user_id=?", (project_id, user_id))
    conn.commit()
    return cur.rowcount > 0


# ── Habilidades ───────────────────────────────────────────────────────────────

def list_skills(conn, user_id):
    return conn.execute(
        "SELECT * FROM skills WHERE user_id=? ORDER BY name ASC",
        (user_id,)
    ).fetchall()

def create_skill(conn, user_id, name, content, description=""):
    cur = conn.execute(
        "INSERT INTO skills (user_id, name, description, content) VALUES (?,?,?,?)",
        (user_id, name, description, content)
    )
    conn.commit()
    return cur.lastrowid

def get_skill(conn, skill_id, user_id):
    return conn.execute(
        "SELECT * FROM skills WHERE id=? AND user_id=?",
        (skill_id, user_id)
    ).fetchone()

def update_skill(conn, skill_id, user_id, name, description, content):
    conn.execute(
        "UPDATE skills SET name=?, description=?, content=?, updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND user_id=?",
        (name, description, content, skill_id, user_id)
    )
    conn.commit()

def delete_skill(conn, skill_id, user_id):
    cur = conn.execute("DELETE FROM skills WHERE id=? AND user_id=?", (skill_id, user_id))
    conn.commit()
    return cur.rowcount > 0


# ── Relación proyecto ↔ habilidades ──────────────────────────────────────────

def get_project_skills(conn, project_id):
    return conn.execute(
        """SELECT s.* FROM skills s
           JOIN project_skills ps ON ps.skill_id = s.id
           WHERE ps.project_id = ?
           ORDER BY ps.position ASC""",
        (project_id,)
    ).fetchall()

def set_project_skills(conn, project_id, skill_ids):
    conn.execute("DELETE FROM project_skills WHERE project_id=?", (project_id,))
    for pos, sid in enumerate(skill_ids):
        conn.execute(
            "INSERT INTO project_skills (project_id, skill_id, position) VALUES (?,?,?)",
            (project_id, sid, pos)
        )
    conn.commit()

def get_project_system_prompt(conn, project_id):
    """Concatena el contenido MD de todas las habilidades del proyecto."""
    skills = get_project_skills(conn, project_id)
    if not skills:
        return ""
    parts = [f"## {s['name']}\n\n{s['content']}" for s in skills]
    return "\n\n---\n\n".join(parts)
