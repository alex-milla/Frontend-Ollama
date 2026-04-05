"""
Blueprint de autenticación.
"""
import re
import functools
from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, flash, g, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash

from .database import get_db
from . import models

bp = Blueprint("auth", __name__)

_MIN_PASSWORD_LEN = 8


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        if g.user["must_change_password"] and request.endpoint != "auth.change_password":
            return redirect(url_for("auth.change_password"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            return {"error": "Acceso denegado"}, 403
        return view(*args, **kwargs)
    return wrapped


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = get_db(current_app.config["DB_PATH"])
        g.user = models.get_user_by_id(db, user_id)
        db.close()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("chat.index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db(current_app.config["DB_PATH"])
        user = models.get_user_by_username(db, username)
        db.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Usuario o contraseña incorrectos."
        else:
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            if user["must_change_password"]:
                return redirect(url_for("auth.change_password"))
            return redirect(url_for("chat.index"))

    return render_template("login.html", error=error)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        db = get_db(current_app.config["DB_PATH"])
        user = models.get_user_by_id(db, g.user["id"])

        if not check_password_hash(user["password_hash"], current_pw):
            error = "La contraseña actual es incorrecta."
        elif len(new_pw) < _MIN_PASSWORD_LEN:
            error = f"La contraseña debe tener al menos {_MIN_PASSWORD_LEN} caracteres."
        elif new_pw != confirm_pw:
            error = "Las contraseñas no coinciden."
        elif new_pw == current_pw:
            error = "La nueva contraseña debe ser diferente a la actual."
        else:
            models.update_password(db, g.user["id"], generate_password_hash(new_pw), must_change=False)
            db.close()
            flash("Contraseña actualizada correctamente.")
            return redirect(url_for("chat.index"))

        db.close()

    return render_template("change_password.html", error=error)
