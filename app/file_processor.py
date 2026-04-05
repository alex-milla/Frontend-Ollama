"""
file_processor.py — Extracción de texto y chunking por tipo de archivo.
"""
import io
import csv
import uuid
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Umbrales
TEXT_LONG_THRESHOLD  = 50_000   # caracteres
TABLE_LONG_THRESHOLD = 500      # filas

CHUNK_SIZES = {
    "block": 10_000,   # caracteres por bloque (TXT / DOCX)
    "row":   100,      # filas por bloque (CSV / XLSX)
    "page":  10,       # páginas por bloque (PDF)  ← unidad; extracción real es 1 pág/vez
}

ALLOWED_EXTENSIONS = {
    "application/pdf":                                          "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain":                                               "txt",
    "text/markdown":                                            "txt",
    "text/x-python":                                            "txt",
    "text/x-python-script":                                     "txt",
    "application/javascript":                                   "txt",
    "application/json":                                         "txt",
    "text/csv":                                                 "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/octet-stream":                                 None,  # se resolverá por extensión
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
    Devuelve lista de unidades de texto:
      - PDF  → lista de páginas (str)
      - DOCX → lista de bloques de ~10 000 caracteres
      - TXT  → lista de bloques de ~10 000 caracteres
      - CSV  → lista de bloques de 100 filas (str con coma)
      - XLSX → lista de bloques de 100 filas por hoja
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
    return [text[i:i+size] for i in range(0, max(1, len(text)), size)]


def _extract_pdf(data: bytes) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages or [""]


def _extract_docx(data: bytes) -> list[str]:
    from docx import Document
    doc = Document(io.BytesIO(data))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    return _chunk_text(full_text, CHUNK_SIZES["block"])


def _extract_txt(data: bytes) -> list[str]:
    try:
        full_text = data.decode("utf-8")
    except UnicodeDecodeError:
        full_text = data.decode("latin-1", errors="replace")
    return _chunk_text(full_text, CHUNK_SIZES["block"])


def _extract_csv(data: bytes) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    # header siempre en el primer bloque
    header = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []
    size = CHUNK_SIZES["row"]
    chunks = []
    if not data_rows:
        return [",".join(header)]
    for i in range(0, len(data_rows), size):
        block = [header] + data_rows[i:i+size]
        chunks.append("\n".join(",".join(r) for r in block))
    return chunks or [""]


def _extract_xlsx(data: bytes) -> list[str]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    chunks = []
    size = CHUNK_SIZES["row"]
    for sheet in wb.worksheets:
        all_rows = list(sheet.iter_rows(values_only=True))
        if not all_rows:
            continue
        header = all_rows[0]
        data_rows = all_rows[1:]
        if not data_rows:
            chunks.append(f"[Hoja: {sheet.title}]\n" + ",".join(str(c or "") for c in header))
            continue
        for i in range(0, len(data_rows), size):
            block = [header] + data_rows[i:i+size]
            text = f"[Hoja: {sheet.title}]\n"
            text += "\n".join(",".join(str(c or "") for c in row) for row in block)
            chunks.append(text)
    return chunks or [""]


# ── Metadatos de chunking ─────────────────────────────────────────────────────

def chunk_unit_for(file_type: str) -> str:
    return {"pdf": "page", "csv": "row", "xlsx": "row"}.get(file_type, "block")


def is_long(chunks: list[str], file_type: str) -> bool:
    if file_type in ("csv", "xlsx"):
        return len(chunks) > 1
    total = sum(len(c) for c in chunks)
    return total > TEXT_LONG_THRESHOLD or len(chunks) > 1


# ── Guardado en disco ─────────────────────────────────────────────────────────

def save_upload(file_bytes: bytes, file_type: str, conv_id: int, upload_folder: str) -> tuple[str, str]:
    """
    Guarda el archivo original y el texto extraído.
    Devuelve (filename_stored, extracted_text_path).
    """
    base = str(uuid.uuid4())
    ext_map = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt", "csv": ".csv", "xlsx": ".xlsx"}
    ext = ext_map.get(file_type, ".bin")

    conv_dir = Path(upload_folder) / str(conv_id)
    conv_dir.mkdir(parents=True, exist_ok=True)
    conv_dir.chmod(0o700)

    # Archivo original
    orig_path = conv_dir / (base + ext)
    orig_path.write_bytes(file_bytes)
    orig_path.chmod(0o600)

    # Texto extraído completo
    chunks = extract_text(file_bytes, file_type)
    full_text = "\n\n--- [CHUNK BOUNDARY] ---\n\n".join(chunks)
    txt_path = conv_dir / (base + ".txt")
    txt_path.write_text(full_text, encoding="utf-8")
    txt_path.chmod(0o600)

    return base + ext, str(txt_path)


def get_chunk_range(extracted_text_path: str, from_idx: int, to_idx: int) -> tuple[str, int]:
    """
    Lee el texto extraído y devuelve el rango de chunks [from_idx, to_idx] (1-based).
    Devuelve (text, total_chunks).
    """
    txt_path = Path(extracted_text_path)
    if not txt_path.exists():
        return "", 0
    full = txt_path.read_text(encoding="utf-8")
    separator = "\n\n--- [CHUNK BOUNDARY] ---\n\n"
    chunks = full.split(separator)
    total = len(chunks)
    from_0 = max(0, from_idx - 1)
    to_0   = min(total, to_idx)
    selected = chunks[from_0:to_0]
    return "\n\n".join(selected), total
