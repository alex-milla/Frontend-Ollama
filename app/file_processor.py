"""
file_processor.py — Extracción de texto y chunking por tipo de archivo.

Criterios de "archivo largo" (requiere selector de rango):
  - PDF:       > 20 páginas  O  texto total > 50 000 caracteres
  - DOCX/TXT:  texto total > 50 000 caracteres
  - CSV/XLSX:  > 500 filas de datos

Para PDFs cortos (≤ 20 páginas y ≤ 50 000 chars) se devuelve un único
chunk con todas las páginas concatenadas, sin molestar al usuario.
"""
import io
import csv
import uuid
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── Umbrales ──────────────────────────────────────────────────────────────────
TEXT_LONG_CHARS  = 50_000   # caracteres totales extraídos
PDF_LONG_PAGES   = 20       # páginas
TABLE_LONG_ROWS  = 500      # filas de datos (sin cabecera)

# Tamaño de cada chunk cuando el archivo SÍ es largo
CHUNK_SIZES = {
    "block": 10_000,   # caracteres (TXT / DOCX)
    "row":   100,      # filas      (CSV / XLSX)
    "page":  10,       # páginas    (PDF largo)
}

ALLOWED_EXTENSIONS = {
    "application/pdf":                                                          "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":  "docx",
    "text/plain":           "txt",
    "text/markdown":        "txt",
    "text/x-python":        "txt",
    "text/x-python-script": "txt",
    "application/javascript": "txt",
    "application/json":     "txt",
    "text/csv":             "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/octet-stream": None,   # se resolverá por extensión
}

EXTENSION_MAP = {
    ".pdf":  "pdf",
    ".docx": "docx",
    ".txt":  "txt",
    ".md":   "txt",
    ".py":   "txt",
    ".js":   "txt",
    ".json": "txt",
    ".csv":  "csv",
    ".xlsx": "xlsx",
}


# ── Resolución de tipo ────────────────────────────────────────────────────────

def resolve_file_type(mime_type: str, filename: str) -> str | None:
    """Devuelve 'pdf', 'docx', 'txt', 'csv', 'xlsx' o None si no soportado."""
    ftype = ALLOWED_EXTENSIONS.get(mime_type)
    if ftype:
        return ftype
    ext = Path(filename).suffix.lower()
    return EXTENSION_MAP.get(ext)


# ── Extracción de texto ───────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, file_type: str) -> list[str]:
    """
    Devuelve lista de chunks de texto listos para enviar al modelo.

    Para archivos cortos devuelve SIEMPRE un único elemento con todo el texto.
    Solo divide en múltiples chunks cuando el archivo supera los umbrales.

      - PDF corto  (≤20 págs, ≤50k chars) → [texto_completo]
      - PDF largo                          → [pág1, pág2, …]  (1 por página)
      - DOCX/TXT corto (≤50k chars)        → [texto_completo]
      - DOCX/TXT largo                     → [bloque1, bloque2, …]
      - CSV/XLSX corto (≤500 filas)        → [texto_completo]
      - CSV/XLSX largo                     → [bloque1, bloque2, …]
    """
    if file_type == "pdf":
        return _extract_pdf(file_bytes)
    elif file_type == "docx":
        return _extract_docx(file_bytes)
    elif file_type == "txt":
        return _extract_txt(file_bytes)
    elif file_type == "csv":
        return _extract_csv(file_bytes)
    elif file_type == "xlsx":
        return _extract_xlsx(file_bytes)
    raise ValueError(f"Tipo de archivo no soportado: {file_type}")


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, max(1, len(text)), size)]


def _extract_pdf(data: bytes) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")

    n_pages    = len(pages_text)
    full_text  = "\n\n".join(pages_text)
    total_chars = len(full_text)

    # Archivo corto: devolver todo en un único chunk
    if n_pages <= PDF_LONG_PAGES and total_chars <= TEXT_LONG_CHARS:
        return [full_text] if full_text.strip() else [""]

    # Archivo largo: un chunk por página (el usuario selecciona el rango)
    return pages_text if pages_text else [""]


def _extract_docx(data: bytes) -> list[str]:
    from docx import Document
    doc       = Document(io.BytesIO(data))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    if len(full_text) <= TEXT_LONG_CHARS:
        return [full_text] if full_text.strip() else [""]
    return _chunk_text(full_text, CHUNK_SIZES["block"])


def _extract_txt(data: bytes) -> list[str]:
    try:
        full_text = data.decode("utf-8")
    except UnicodeDecodeError:
        full_text = data.decode("latin-1", errors="replace")
    if len(full_text) <= TEXT_LONG_CHARS:
        return [full_text] if full_text.strip() else [""]
    return _chunk_text(full_text, CHUNK_SIZES["block"])


def _extract_csv(data: bytes) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    reader    = csv.reader(io.StringIO(text))
    rows      = list(reader)
    header    = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []

    if not data_rows:
        return [",".join(header)]

    # Archivo corto: devolver todo en un único chunk
    if len(data_rows) <= TABLE_LONG_ROWS:
        all_rows = [header] + data_rows
        return ["\n".join(",".join(r) for r in all_rows)]

    # Archivo largo: bloques de CHUNK_SIZES["row"] filas, siempre con cabecera
    chunks = []
    size   = CHUNK_SIZES["row"]
    for i in range(0, len(data_rows), size):
        block = [header] + data_rows[i:i + size]
        chunks.append("\n".join(",".join(r) for r in block))
    return chunks or [""]


def _extract_xlsx(data: bytes) -> list[str]:
    import openpyxl
    wb     = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    chunks = []
    size   = CHUNK_SIZES["row"]

    # Contar filas totales para decidir si es corto
    total_data_rows = 0
    sheets_data = []
    for sheet in wb.worksheets:
        all_rows  = list(sheet.iter_rows(values_only=True))
        header    = all_rows[0] if all_rows else ()
        data_rows = all_rows[1:] if len(all_rows) > 1 else []
        total_data_rows += len(data_rows)
        sheets_data.append((sheet.title, header, data_rows))

    # Archivo corto: todo en un único chunk
    if total_data_rows <= TABLE_LONG_ROWS:
        lines = []
        for title, header, data_rows in sheets_data:
            if not data_rows:
                continue
            lines.append(f"[Hoja: {title}]")
            lines.append(",".join(str(c or "") for c in header))
            for row in data_rows:
                lines.append(",".join(str(c or "") for c in row))
        return ["\n".join(lines)] if lines else [""]

    # Archivo largo: bloques con cabecera por hoja
    for title, header, data_rows in sheets_data:
        if not data_rows:
            continue
        for i in range(0, len(data_rows), size):
            block = [header] + data_rows[i:i + size]
            text  = f"[Hoja: {title}]\n"
            text += "\n".join(",".join(str(c or "") for c in row) for row in block)
            chunks.append(text)
    return chunks or [""]


# ── Metadatos de chunking ─────────────────────────────────────────────────────

def chunk_unit_for(file_type: str) -> str:
    return {"pdf": "page", "csv": "row", "xlsx": "row"}.get(file_type, "block")


def is_long(chunks: list[str], file_type: str) -> bool:
    """
    Devuelve True solo si el archivo supera los umbrales y necesita
    que el usuario seleccione un rango manualmente.
    """
    return len(chunks) > 1


# ── Guardado en disco ─────────────────────────────────────────────────────────

def save_upload(file_bytes: bytes, file_type: str, conv_id: int,
                upload_folder: str) -> tuple[str, str]:
    """
    Guarda el archivo original y el texto extraído.
    Devuelve (filename_stored, extracted_text_path).
    """
    base    = str(uuid.uuid4())
    ext_map = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt",
               "csv": ".csv", "xlsx": ".xlsx"}
    ext     = ext_map.get(file_type, ".bin")

    conv_dir = Path(upload_folder) / str(conv_id)
    conv_dir.mkdir(parents=True, exist_ok=True)
    conv_dir.chmod(0o700)

    # Archivo original
    orig_path = conv_dir / (base + ext)
    orig_path.write_bytes(file_bytes)
    orig_path.chmod(0o600)

    # Texto extraído completo (con separadores de chunk para archivos largos)
    chunks    = extract_text(file_bytes, file_type)
    full_text = "\n\n--- [CHUNK BOUNDARY] ---\n\n".join(chunks)
    txt_path  = conv_dir / (base + ".txt")
    txt_path.write_text(full_text, encoding="utf-8")
    txt_path.chmod(0o600)

    return base + ext, str(txt_path)


def get_chunk_range(extracted_text_path: str, from_idx: int,
                    to_idx: int) -> tuple[str, int]:
    """
    Lee el texto extraído y devuelve el rango [from_idx, to_idx] (1-based).
    Devuelve (text, total_chunks).
    """
    txt_path = Path(extracted_text_path)
    if not txt_path.exists():
        return "", 0
    full      = txt_path.read_text(encoding="utf-8")
    separator = "\n\n--- [CHUNK BOUNDARY] ---\n\n"
    chunks    = full.split(separator)
    total     = len(chunks)
    from_0    = max(0, from_idx - 1)
    to_0      = min(total, to_idx)
    return "\n\n".join(chunks[from_0:to_0]), total
