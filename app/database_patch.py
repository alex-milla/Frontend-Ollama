"""
database_patch.py — Fragmento de migración para Sesión 4.
Este contenido debe integrarse en database.py del proyecto existente.

INSTRUCCIONES DE INTEGRACIÓN:
1. En _SCHEMA, añadir las dos tablas nuevas y sus índices (ver abajo).
2. En _migrate(), añadir el bloque "Migración Sesión 4" (ver abajo).
3. En Config, añadir OUTPUT_FOLDER (ver config_patch.py).
"""

# ════════════════════════════════════════════════════════════════════════════════
# AÑADIR AL FINAL DE _SCHEMA (antes del último """):
# ════════════════════════════════════════════════════════════════════════════════

SCHEMA_ADDITION = """
CREATE TABLE IF NOT EXISTS conversation_attachments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id     INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    filename_stored     TEXT    NOT NULL,
    original_name       TEXT    NOT NULL,
    mime_type           TEXT    NOT NULL,
    size_bytes          INTEGER NOT NULL,
    chunk_unit          TEXT    NOT NULL DEFAULT 'page',
    chunk_count         INTEGER NOT NULL DEFAULT 1,
    extracted_text_path TEXT    NOT NULL,
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS project_outputs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    conversation_id     INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    filename_stored     TEXT    NOT NULL,
    display_name        TEXT    NOT NULL,
    format              TEXT    NOT NULL,
    template            TEXT    NOT NULL DEFAULT 'libre',
    size_bytes          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_attachments_conv ON conversation_attachments(conversation_id);
CREATE INDEX IF NOT EXISTS idx_outputs_project  ON project_outputs(project_id);
"""

# ════════════════════════════════════════════════════════════════════════════════
# AÑADIR EN _migrate() — después del bloque de project_skills:
# ════════════════════════════════════════════════════════════════════════════════

MIGRATION_ADDITION = """
    # Sesión 4: tabla conversation_attachments
    if "conversations" in tables and "conversation_attachments" not in tables:
        log.info("Migración: creando tabla conversation_attachments")
        conn.execute('''
            CREATE TABLE conversation_attachments (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id     INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                filename_stored     TEXT    NOT NULL,
                original_name       TEXT    NOT NULL,
                mime_type           TEXT    NOT NULL,
                size_bytes          INTEGER NOT NULL,
                chunk_unit          TEXT    NOT NULL DEFAULT 'page',
                chunk_count         INTEGER NOT NULL DEFAULT 1,
                extracted_text_path TEXT    NOT NULL,
                created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )
        ''')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attachments_conv ON conversation_attachments(conversation_id)")

    # Sesión 4: tabla project_outputs
    if "projects" in tables and "project_outputs" not in tables:
        log.info("Migración: creando tabla project_outputs")
        conn.execute('''
            CREATE TABLE project_outputs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                conversation_id     INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
                filename_stored     TEXT    NOT NULL,
                display_name        TEXT    NOT NULL,
                format              TEXT    NOT NULL,
                template            TEXT    NOT NULL DEFAULT 'libre',
                size_bytes          INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )
        ''')
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outputs_project ON project_outputs(project_id)")

    conn.commit()
"""
