"""
Blueprint de administración.
Solo accesible por usuarios con role='admin'.
"""
import secrets
from flask import Blueprint, g, jsonify, request, render_template, current_app
from werkzeug.security import generate_password_hash

from .auth import admin_required
from .database import get_db
from . import models, ollama_client

bp = Blueprint("admin", __name__, url_prefix="/admin")

_MIN_USERNAME_LEN = 3
_MAX_USERNAME_LEN = 64
_MIN_PASSWORD_LEN = 8


@bp.route("/")
@admin_required
def index():
    return render_template("admin.html", user=g.user)


@bp.route("/api/users", methods=["GET"])
@admin_required
def api_list_users():
    db = get_db(current_app.config["DB_PATH"])
    users = models.list_users(db)
    db.close()
    return jsonify([dict(u) for u in users])


@bp.route("/api/users", methods=["POST"])
@admin_required
def api_create_user():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    role     = str(data.get("role", "user")).strip()

    if len(username) < _MIN_USERNAME_LEN or len(username) > _MAX_USERNAME_LEN:
        return jsonify({"error": f"El nombre de usuario debe tener entre {_MIN_USERNAME_LEN} y {_MAX_USERNAME_LEN} caracteres."}), 400
    if len(password) < _MIN_PASSWORD_LEN:
        return jsonify({"error": f"La contraseña debe tener al menos {_MIN_PASSWORD_LEN} caracteres."}), 400
    if role not in ("admin", "user"):
        return jsonify({"error": "Rol inválido."}), 400

    db = get_db(current_app.config["DB_PATH"])
    existing = models.get_user_by_username(db, username)
    if existing:
        db.close()
        return jsonify({"error": "El nombre de usuario ya existe."}), 409

    user_id = models.create_user(db, username, generate_password_hash(password), role)
    db.close()
    return jsonify({"ok": True, "id": user_id}), 201


@bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    if user_id == g.user["id"]:
        return jsonify({"error": "No puedes eliminar tu propia cuenta."}), 400

    db = get_db(current_app.config["DB_PATH"])
    user = models.get_user_by_id(db, user_id)
    if user is None:
        db.close()
        return jsonify({"error": "Usuario no encontrado."}), 404

    models.delete_user(db, user_id)
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/users/<int:user_id>/reset-password", methods=["PUT"])
@admin_required
def api_reset_password(user_id):
    db = get_db(current_app.config["DB_PATH"])
    user = models.get_user_by_id(db, user_id)
    if user is None:
        db.close()
        return jsonify({"error": "Usuario no encontrado."}), 404

    temp_pw = secrets.token_urlsafe(9)
    models.update_password(db, user_id, generate_password_hash(temp_pw), must_change=True)
    db.close()
    return jsonify({"ok": True, "temp_password": temp_pw})


@bp.route("/api/check-update", methods=["GET"])
@admin_required
def api_check_update():
    import json, urllib.request, urllib.error
    try:
        url = "https://api.github.com/repos/alex-milla/Frontend-Ollama/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "Frontend-Ollama"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        latest  = data.get("tag_name", "").lstrip("v")
        current = _read_version()
        return jsonify({"latest": latest, "current": current, "update_available": latest != current and bool(latest)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


def _read_version() -> str:
    from pathlib import Path
    v = Path(current_app.root_path).parent / "VERSION"
    return v.read_text().strip() if v.exists() else "unknown"
