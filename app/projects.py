"""
Blueprint de proyectos, habilidades y outputs.
"""
from flask import Blueprint, g, jsonify, request, render_template, current_app
from .auth import login_required
from .database import get_db
from . import models

bp = Blueprint("projects", __name__, url_prefix="/projects")

_MAX_NAME = 128
_MAX_DESC = 512
_MAX_CONTENT = 64 * 1024


@bp.route("/")
@login_required
def index():
    return render_template("projects.html", user=g.user)


@bp.route("/api/projects", methods=["GET"])
@login_required
def api_list_projects():
    db = get_db(current_app.config["DB_PATH"])
    projects = models.list_projects(db, g.user["id"])
    db.close()
    return jsonify([dict(p) for p in projects])


@bp.route("/api/projects", methods=["POST"])
@login_required
def api_create_project():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:_MAX_NAME]
    description = str(data.get("description", "")).strip()[:_MAX_DESC]
    if not name:
        return jsonify({"error": "El nombre es obligatorio."}), 400
    db = get_db(current_app.config["DB_PATH"])
    pid = models.create_project(db, g.user["id"], name, description)
    project = models.get_project(db, pid, g.user["id"])
    db.close()
    return jsonify(dict(project)), 201


@bp.route("/api/projects/<int:project_id>", methods=["GET"])
@login_required
def api_get_project(project_id):
    db = get_db(current_app.config["DB_PATH"])
    project = models.get_project(db, project_id, g.user["id"])
    if project is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    skills = models.get_project_skills(db, project_id)
    all_skills = models.list_skills(db, g.user["id"])
    db.close()
    return jsonify({
        "project": dict(project),
        "skills": [dict(s) for s in skills],
        "all_skills": [dict(s) for s in all_skills],
    })


@bp.route("/api/projects/<int:project_id>", methods=["PUT"])
@login_required
def api_update_project(project_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:_MAX_NAME]
    description = str(data.get("description", "")).strip()[:_MAX_DESC]
    if not name:
        return jsonify({"error": "El nombre es obligatorio."}), 400
    db = get_db(current_app.config["DB_PATH"])
    if models.get_project(db, project_id, g.user["id"]) is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    models.update_project(db, project_id, g.user["id"], name, description)
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/projects/<int:project_id>", methods=["DELETE"])
@login_required
def api_delete_project(project_id):
    db = get_db(current_app.config["DB_PATH"])
    deleted = models.delete_project(db, project_id, g.user["id"])
    db.close()
    if not deleted:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify({"ok": True})


@bp.route("/api/projects/<int:project_id>/skills", methods=["PUT"])
@login_required
def api_set_project_skills(project_id):
    data = request.get_json(silent=True) or {}
    skill_ids = data.get("skill_ids", [])
    if not isinstance(skill_ids, list):
        return jsonify({"error": "skill_ids debe ser una lista."}), 400
    db = get_db(current_app.config["DB_PATH"])
    if models.get_project(db, project_id, g.user["id"]) is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    for sid in skill_ids:
        if models.get_skill(db, sid, g.user["id"]) is None:
            db.close()
            return jsonify({"error": f"Habilidad {sid} no encontrada."}), 404
    models.set_project_skills(db, project_id, skill_ids)
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/projects/<int:project_id>/system-prompt", methods=["GET"])
@login_required
def api_project_system_prompt(project_id):
    db = get_db(current_app.config["DB_PATH"])
    if models.get_project(db, project_id, g.user["id"]) is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    prompt = models.get_project_system_prompt(db, project_id)
    db.close()
    return jsonify({"system_prompt": prompt})


@bp.route("/api/projects/<int:project_id>/outputs", methods=["GET"])
@login_required
def api_project_outputs(project_id):
    db = get_db(current_app.config["DB_PATH"])
    project = models.get_project(db, project_id, g.user["id"])
    if project is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    outputs = models.list_outputs(db, project_id)
    db.close()
    return jsonify([dict(o) for o in outputs])


@bp.route("/api/skills", methods=["GET"])
@login_required
def api_list_skills():
    db = get_db(current_app.config["DB_PATH"])
    skills = models.list_skills(db, g.user["id"])
    db.close()
    return jsonify([dict(s) for s in skills])


@bp.route("/api/skills", methods=["POST"])
@login_required
def api_create_skill():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:_MAX_NAME]
    description = str(data.get("description", "")).strip()[:_MAX_DESC]
    content = str(data.get("content", "")).strip()[:_MAX_CONTENT]
    if not name:
        return jsonify({"error": "El nombre es obligatorio."}), 400
    if not content:
        return jsonify({"error": "El contenido es obligatorio."}), 400
    db = get_db(current_app.config["DB_PATH"])
    sid = models.create_skill(db, g.user["id"], name, content, description)
    skill = models.get_skill(db, sid, g.user["id"])
    db.close()
    return jsonify(dict(skill)), 201


@bp.route("/api/skills/<int:skill_id>", methods=["GET"])
@login_required
def api_get_skill(skill_id):
    db = get_db(current_app.config["DB_PATH"])
    skill = models.get_skill(db, skill_id, g.user["id"])
    db.close()
    if skill is None:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify(dict(skill))


@bp.route("/api/skills/<int:skill_id>", methods=["PUT"])
@login_required
def api_update_skill(skill_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:_MAX_NAME]
    description = str(data.get("description", "")).strip()[:_MAX_DESC]
    content = str(data.get("content", "")).strip()[:_MAX_CONTENT]
    if not name or not content:
        return jsonify({"error": "Nombre y contenido son obligatorios."}), 400
    db = get_db(current_app.config["DB_PATH"])
    if models.get_skill(db, skill_id, g.user["id"]) is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    models.update_skill(db, skill_id, g.user["id"], name, description, content)
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/skills/<int:skill_id>", methods=["DELETE"])
@login_required
def api_delete_skill(skill_id):
    db = get_db(current_app.config["DB_PATH"])
    deleted = models.delete_skill(db, skill_id, g.user["id"])
    db.close()
    if not deleted:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify({"ok": True})
