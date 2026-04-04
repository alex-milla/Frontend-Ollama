"""
Blueprint de chat con soporte de proyectos y system prompt de habilidades.
"""
import json
import xml.etree.ElementTree as ET
from flask import (
    Blueprint, Response, g, jsonify, request,
    render_template, stream_with_context, current_app
)

from .auth import login_required, admin_required
from .database import get_db
from . import models, ollama_client

bp = Blueprint("chat", __name__)


def _ollama_host():
    db = get_db(current_app.config["DB_PATH"])
    host = models.get_setting(db, "ollama_host") or current_app.config["OLLAMA_HOST"]
    db.close()
    return host


# ── Vistas HTML ───────────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    return render_template("chat.html", user=g.user)


# ── API: Modelos ───────────────────────────────────────────────────────────────

@bp.route("/api/models")
@login_required
def api_models():
    host = _ollama_host()
    raw = ollama_client.list_models(host)
    names = [m.get("name", "") for m in raw if m.get("name")]
    return jsonify({"models": names})


@bp.route("/api/ollama/status")
@login_required
def api_ollama_status():
    host = _ollama_host()
    result = ollama_client.check_connection(host)
    result["host"] = host
    return jsonify(result)


# ── API: Conversaciones ────────────────────────────────────────────────────────

@bp.route("/api/conversations", methods=["GET"])
@login_required
def api_list_conversations():
    project_id = request.args.get("project_id", type=int)
    db = get_db(current_app.config["DB_PATH"])
    if project_id:
        convs = db.execute(
            "SELECT id,title,model,project_id,created_at,updated_at FROM conversations WHERE user_id=? AND project_id=? ORDER BY updated_at DESC",
            (g.user["id"], project_id)
        ).fetchall()
    else:
        convs = db.execute(
            "SELECT id,title,model,project_id,created_at,updated_at FROM conversations WHERE user_id=? AND project_id IS NULL ORDER BY updated_at DESC",
            (g.user["id"],)
        ).fetchall()
    db.close()
    return jsonify([dict(c) for c in convs])


@bp.route("/api/conversations", methods=["POST"])
@login_required
def api_create_conversation():
    data = request.get_json(silent=True) or {}
    model = str(data.get("model", "")).strip()[:128]
    project_id = data.get("project_id")
    db = get_db(current_app.config["DB_PATH"])
    conv_id = models.create_conversation(db, g.user["id"], model, project_id)
    conv = models.get_conversation(db, conv_id, g.user["id"])
    db.close()
    return jsonify(dict(conv)), 201


@bp.route("/api/conversations/<int:conv_id>", methods=["GET"])
@login_required
def api_get_conversation(conv_id):
    db = get_db(current_app.config["DB_PATH"])
    conv = models.get_conversation(db, conv_id, g.user["id"])
    if conv is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    msgs = models.list_messages(db, conv_id)
    db.close()
    return jsonify({"conversation": dict(conv), "messages": [dict(m) for m in msgs]})


@bp.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
@login_required
def api_delete_conversation(conv_id):
    db = get_db(current_app.config["DB_PATH"])
    deleted = models.delete_conversation(db, conv_id, g.user["id"])
    db.close()
    if not deleted:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify({"ok": True})


@bp.route("/api/conversations/<int:conv_id>/export")
@login_required
def api_export_conversation(conv_id):
    db = get_db(current_app.config["DB_PATH"])
    conv = models.get_conversation(db, conv_id, g.user["id"])
    if conv is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    msgs = models.list_messages(db, conv_id)
    db.close()

    root = ET.Element("conversation")
    meta = ET.SubElement(root, "metadata")
    ET.SubElement(meta, "title").text = conv["title"]
    ET.SubElement(meta, "model").text = conv["model"]
    ET.SubElement(meta, "created").text = conv["created_at"]
    ET.SubElement(meta, "messages_count").text = str(len(msgs))

    messages_el = ET.SubElement(root, "messages")
    for m in msgs:
        msg_el = ET.SubElement(messages_el, "message")
        msg_el.set("role", m["role"])
        msg_el.set("timestamp", m["created_at"])
        msg_el.text = m["content"]

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")
    filename = f"conversacion-{conv_id}.xml"
    return Response(
        xml_str,
        mimetype="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── API: Chat con streaming SSE ───────────────────────────────────────────────

@bp.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    conv_id     = data.get("conversation_id")
    model       = str(data.get("model", "")).strip()[:128]
    content     = str(data.get("message", "")).strip()
    project_id  = data.get("project_id")
    # skill_ids: habilidades que el usuario ha activado para esta conversación
    skill_ids   = data.get("skill_ids", [])

    if not content or not model:
        return jsonify({"error": "Faltan campos requeridos"}), 400

    db = get_db(current_app.config["DB_PATH"])

    if conv_id:
        conv = models.get_conversation(db, conv_id, g.user["id"])
        if conv is None:
            db.close()
            return jsonify({"error": "Conversación no encontrada"}), 404
        project_id = conv["project_id"]
    else:
        conv_id = models.create_conversation(db, g.user["id"], model, project_id)

    models.add_message(db, conv_id, "user", content)

    conv = models.get_conversation(db, conv_id, g.user["id"])
    if conv["title"] == "Nueva conversación":
        title = content[:60] + ("…" if len(content) > 60 else "")
        models.update_conversation_title(db, conv_id, title)

    history = models.list_messages(db, conv_id)
    ollama_msgs = [{"role": m["role"], "content": m["content"]} for m in history]

    # Inyectar system prompt: habilidades seleccionadas por el usuario
    system_prompt = ""
    if skill_ids:
        # Habilidades seleccionadas manualmente para esta petición
        parts = []
        for sid in skill_ids:
            skill = models.get_skill(db, sid, g.user["id"])
            if skill:
                parts.append(f"## {skill['name']}\n\n{skill['content']}")
        system_prompt = "\n\n---\n\n".join(parts)
    elif project_id:
        # Fallback: todas las habilidades del proyecto
        system_prompt = models.get_project_system_prompt(db, project_id)

    if system_prompt:
        ollama_msgs = [{"role": "system", "content": system_prompt}] + ollama_msgs

    db.close()

    host = _ollama_host()

    def generate():
        full_response = []
        yield f"data: {json.dumps({'conv_id': conv_id})}\n\n"

        for token in ollama_client.stream_chat(host, model, ollama_msgs):
            if token == "[DONE]":
                response_text = "".join(full_response)
                db2 = get_db(current_app.config["DB_PATH"])
                models.add_message(db2, conv_id, "assistant", response_text)
                models.touch_conversation(db2, conv_id)
                db2.close()
                yield "data: [DONE]\n\n"
                return
            elif token.startswith("[ERROR]"):
                yield f"data: {json.dumps({'error': token})}\n\n"
                return
            else:
                full_response.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── API: Settings (admin) ─────────────────────────────────────────────────────

@bp.route("/api/settings/ollama", methods=["PUT"])
@admin_required
def api_update_ollama():
    data = request.get_json(silent=True) or {}
    host = str(data.get("host", "")).strip()
    if not host:
        return jsonify({"error": "Host requerido"}), 400
    if not (host.startswith("http://") or host.startswith("https://")):
        return jsonify({"error": "El host debe empezar con http:// o https://"}), 400
    db = get_db(current_app.config["DB_PATH"])
    models.set_setting(db, "ollama_host", host)
    db.close()
    return jsonify({"ok": True, "host": host})
