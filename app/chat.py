"""
Blueprint de chat con soporte de proyectos, habilidades, adjuntos y exportación.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from flask import (
    Blueprint, Response, g, jsonify, request, send_file,
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


@bp.route("/")
@login_required
def index():
    return render_template("chat.html", user=g.user)


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


@bp.route("/api/conversations", methods=["GET"])
@login_required
def api_list_conversations():
    project_id = request.args.get("project_id", type=int)
    db = get_db(current_app.config["DB_PATH"])
    if project_id:
        convs = db.execute(
            "SELECT id,title,model,project_id,created_at,updated_at FROM conversations"
            " WHERE user_id=? AND project_id=? ORDER BY updated_at DESC",
            (g.user["id"], project_id)
        ).fetchall()
    else:
        convs = db.execute(
            "SELECT id,title,model,project_id,created_at,updated_at FROM conversations"
            " WHERE user_id=? AND project_id IS NULL ORDER BY updated_at DESC",
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


@bp.route("/api/conversations/<int:conv_id>/move", methods=["PATCH"])
@login_required
def api_move_conversation(conv_id):
    data = request.get_json(silent=True) or {}
    project_id = data.get("project_id")
    db = get_db(current_app.config["DB_PATH"])
    conv = models.get_conversation(db, conv_id, g.user["id"])
    if conv is None:
        db.close()
        return jsonify({"error": "No encontrado"}), 404
    db.execute(
        "UPDATE conversations SET project_id=?,"
        " updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')"
        " WHERE id=? AND user_id=?",
        (project_id, conv_id, g.user["id"])
    )
    db.commit()
    db.close()
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


@bp.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    conv_id    = data.get("conversation_id")
    model      = str(data.get("model", "")).strip()[:128]
    content    = str(data.get("message", "")).strip()
    project_id = data.get("project_id")
    skill_ids  = data.get("skill_ids", [])

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

    system_prompt = ""
    if skill_ids:
        parts = []
        for sid in skill_ids:
            skill = models.get_skill(db, sid, g.user["id"])
            if skill:
                parts.append(f"## {skill['name']}\n\n{skill['content']}")
        system_prompt = "\n\n---\n\n".join(parts)
    elif project_id:
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


# ── Adjuntos ──────────────────────────────────────────────────────────────────

@bp.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    from . import file_processor as fp
    from werkzeug.utils import secure_filename

    if "file" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "Archivo vacío"}), 400

    conv_id = request.form.get("conversation_id", type=int)
    original_name = secure_filename(f.filename)
    mime_type = f.content_type or "application/octet-stream"
    file_bytes = f.read()
    size_bytes = len(file_bytes)

    file_type = fp.resolve_file_type(mime_type, original_name)
    if file_type is None:
        return jsonify({"error": f"Tipo de archivo no soportado: {original_name}"}), 415

    # Necesitamos un conv_id para guardar; si no hay, creamos una conversación temporal
    db = get_db(current_app.config["DB_PATH"])
    if not conv_id:
        model = request.form.get("model", "")
        conv_id = models.create_conversation(db, g.user["id"], model, None)

    # Verificar que la conversación pertenece al usuario
    conv = models.get_conversation(db, conv_id, g.user["id"])
    if conv is None:
        db.close()
        return jsonify({"error": "Conversación no encontrada"}), 404

    try:
        chunks = fp.extract_text(file_bytes, file_type)
    except Exception as exc:
        db.close()
        return jsonify({"error": f"Error extrayendo texto: {exc}"}), 422

    chunk_unit = fp.chunk_unit_for(file_type)
    chunk_count = len(chunks)
    long_file = fp.is_long(chunks, file_type)

    filename_stored, extracted_text_path = fp.save_upload(
        file_bytes, file_type, conv_id,
        current_app.config["UPLOAD_FOLDER"]
    )

    att_id = models.create_attachment(
        db, conv_id, filename_stored, original_name,
        mime_type, size_bytes, chunk_unit, chunk_count, extracted_text_path
    )
    db.close()

    preview_chunk = chunks[0][:2000] if chunks else ""

    return jsonify({
        "attachment_id": att_id,
        "conversation_id": conv_id,
        "original_name": original_name,
        "chunk_unit": chunk_unit,
        "chunk_count": chunk_count,
        "is_long": long_file,
        "preview_chunk": preview_chunk,
    }), 201


@bp.route("/api/attachments/<int:attachment_id>/range")
@login_required
def api_attachment_range(attachment_id):
    from . import file_processor as fp

    from_idx = request.args.get("from", 1, type=int)
    to_idx   = request.args.get("to", 10, type=int)

    db = get_db(current_app.config["DB_PATH"])
    att = models.get_attachment(db, attachment_id)
    if att is None:
        db.close()
        return jsonify({"error": "Adjunto no encontrado"}), 404

    # Verificar que la conversación pertenece al usuario
    conv = models.get_conversation(db, att["conversation_id"], g.user["id"])
    db.close()
    if conv is None:
        return jsonify({"error": "Acceso denegado"}), 403

    text, total = fp.get_chunk_range(att["extracted_text_path"], from_idx, to_idx)
    return jsonify({
        "text": text,
        "chunk_unit": att["chunk_unit"],
        "from": from_idx,
        "to": to_idx,
        "total": total,
    })


@bp.route("/api/attachments/<int:attachment_id>", methods=["DELETE"])
@login_required
def api_delete_attachment(attachment_id):
    import os
    db = get_db(current_app.config["DB_PATH"])
    att = models.get_attachment(db, attachment_id)
    if att is None:
        db.close()
        return jsonify({"error": "Adjunto no encontrado"}), 404

    conv = models.get_conversation(db, att["conversation_id"], g.user["id"])
    if conv is None:
        db.close()
        return jsonify({"error": "Acceso denegado"}), 403

    # Borrar archivos en disco
    txt_path = Path(att["extracted_text_path"])
    if txt_path.exists():
        txt_path.unlink()

    # El archivo original está en el mismo directorio con el mismo uuid pero extensión original
    orig_dir = txt_path.parent
    stem = txt_path.stem
    for p in orig_dir.glob(stem + ".*"):
        if p.suffix != ".txt":
            p.unlink()

    models.delete_attachment(db, attachment_id)
    db.close()
    return jsonify({"ok": True})


# ── Exportar ──────────────────────────────────────────────────────────────────

@bp.route("/api/export", methods=["POST"])
@login_required
def api_export():
    from . import file_exporter as fe

    data = request.get_json(silent=True) or {}
    text        = str(data.get("text", "")).strip()
    fmt         = str(data.get("format", "txt")).lower()
    template    = str(data.get("template", "libre")).lower()
    filename    = str(data.get("filename", "documento")).strip()[:128] or "documento"
    project_id  = data.get("project_id")
    conv_id     = data.get("conversation_id")

    if not text:
        return jsonify({"error": "El texto no puede estar vacío"}), 400
    if fmt not in fe.FORMATS:
        return jsonify({"error": f"Formato no soportado: {fmt}"}), 400
    if template not in fe.TEMPLATES:
        template = "libre"

    try:
        file_bytes, mime = fe.generate(text, fmt, template)
    except Exception as exc:
        return jsonify({"error": f"Error generando archivo: {exc}"}), 500

    display_name = filename + "." + fmt

    if project_id:
        db = get_db(current_app.config["DB_PATH"])
        project = models.get_project(db, project_id, g.user["id"])
        if project is None:
            db.close()
            return jsonify({"error": "Proyecto no encontrado"}), 404

        filename_stored, _ = fe.save_output(
            file_bytes, fmt, display_name, project_id,
            current_app.config["OUTPUT_FOLDER"]
        )
        output_id = models.create_output(
            db, project_id, conv_id, filename_stored,
            display_name, fmt, template, len(file_bytes)
        )
        db.close()
        return jsonify({
            "output_id": output_id,
            "download_url": f"/api/outputs/{output_id}/download",
        }), 201
    else:
        # Descarga directa
        import io
        return Response(
            file_bytes,
            mimetype=mime,
            headers={
                "Content-Disposition": f'attachment; filename="{display_name}"',
                "Content-Length": str(len(file_bytes)),
            }
        )


@bp.route("/api/outputs/<int:output_id>/download")
@login_required
def api_download_output(output_id):
    from . import file_exporter as fe

    db = get_db(current_app.config["DB_PATH"])
    output = models.get_output(db, output_id)
    if output is None:
        db.close()
        return jsonify({"error": "Archivo no encontrado"}), 404

    # Verificar que el proyecto pertenece al usuario
    project = models.get_project(db, output["project_id"], g.user["id"])
    db.close()
    if project is None:
        return jsonify({"error": "Acceso denegado"}), 403

    fpath = Path(current_app.config["OUTPUT_FOLDER"]) / str(output["project_id"]) / output["filename_stored"]
    if not fpath.exists():
        return jsonify({"error": "Archivo no encontrado en disco"}), 404

    mime = fe._mime(output["format"])
    return send_file(
        str(fpath),
        mimetype=mime,
        as_attachment=True,
        download_name=output["display_name"],
    )


@bp.route("/api/outputs/<int:output_id>", methods=["DELETE"])
@login_required
def api_delete_output(output_id):
    db = get_db(current_app.config["DB_PATH"])
    output = models.get_output(db, output_id)
    if output is None:
        db.close()
        return jsonify({"error": "Archivo no encontrado"}), 404

    project = models.get_project(db, output["project_id"], g.user["id"])
    if project is None:
        db.close()
        return jsonify({"error": "Acceso denegado"}), 403

    # Borrar de disco
    fpath = Path(current_app.config["OUTPUT_FOLDER"]) / str(output["project_id"]) / output["filename_stored"]
    if fpath.exists():
        fpath.unlink()

    models.delete_output(db, output_id)
    db.close()
    return jsonify({"ok": True})
