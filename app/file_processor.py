"""
file_processor.py — Extracción de texto y chunking por tipo de archivo.
Sesión 5 (v3): OCR de imágenes con Tesseract (pytesseract).
               Tesseract es preciso para texto impreso, capturas y documentos.
"""
import io
import csv
import uuid
import base64
import logging
from pathlib import Path

log = logging.getLogger(__name__)

TEXT_LONG_CHARS  = 50_000
PDF_LONG_PAGES   = 20
TABLE_LONG_ROWS  = 500

CHUNK_SIZES = {
    "block": 10_000,
    "row":   100,
    "page":  10,
}

ALLOWED_EXTENSIONS = {
    "application/pdf":                                                          "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":  "docx",
    "text/plain":             "txt",
    "text/markdown":          "txt",
    "text/x-python":          "txt",
    "text/x-python-script":   "txt",
    "application/javascript": "txt",
    "application/json":       "txt",
    "text/csv":               "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "image/jpeg":             "image",
    "image/jpg":              "image",
    "image/png":              "image",
    "image/webp":             "image",
    "application/octet-stream": None,
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
    ".jpg":  "image",
    ".jpeg": "image",
    ".png":  "image",
    ".webp": "image",
}

VISION_MODEL_HINTS = [
    "llava", "moondream", "vision", "minicpm-v", "bakllava",
    "cogvlm", "qwen-vl", "internvl",
]


def resolve_file_type(mime_type: str, filename: str) -> str | None:
    ftype = ALLOWED_EXTENSIONS.get(mime_type)
    if ftype:
        return ftype
    ext = Path(filename).suffix.lower()
    return EXTENSION_MAP.get(ext)


def is_vision_model(model_name: str) -> bool:
    name_lower = (model_name or "").lower()
    return any(hint in name_lower for hint in VISION_MODEL_HINTS)


def tesseract_available() -> bool:
    """Comprueba si pytesseract y Tesseract están instalados."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_text(file_bytes: bytes, file_type: str,
                 ollama_host: str = "", model: str = "") -> list[str]:
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
    elif file_type == "image":
        return _extract_image_tesseract(file_bytes)
    raise ValueError(f"Tipo de archivo no soportado: {file_type}")


# ── OCR con Tesseract ─────────────────────────────────────────────────────────

def _extract_image_tesseract(data: bytes) -> list[str]:
    """
    Extrae texto de una imagen usando Tesseract OCR.
    Detecta automáticamente si el texto es español o inglés.
    Devuelve lista de un único chunk con el texto extraído.
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ValueError(
            "Tesseract no está instalado. Ejecuta: "
            "apt-get install tesseract-ocr tesseract-ocr-spa && "
            "pip install pytesseract pillow --break-system-packages"
        )

    try:
        image = Image.open(io.BytesIO(data))

        # Convertir a RGB si es necesario (PNG con transparencia, etc.)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Intentar con español + inglés primero (cubre la mayoría de casos)
        # Si falla el idioma spa, caer a eng solo
        langs = _available_tesseract_langs()
        if "spa" in langs and "eng" in langs:
            lang = "spa+eng"
        elif "spa" in langs:
            lang = "spa"
        else:
            lang = "eng"

        # Configuración optimizada para capturas de pantalla y documentos
        # PSM 6: asume bloque de texto uniforme (mejor para capturas)
        # PSM 3: detección automática (mejor para documentos con layout)
        # Probamos PSM 6 primero, si el resultado es corto probamos PSM 3
        config_6 = "--psm 6 --oem 3"
        config_3 = "--psm 3 --oem 3"

        text_6 = pytesseract.image_to_string(image, lang=lang, config=config_6).strip()
        text_3 = pytesseract.image_to_string(image, lang=lang, config=config_3).strip()

        # Usar el resultado más largo (más texto extraído = mejor)
        text = text_6 if len(text_6) >= len(text_3) else text_3

        if not text:
            raise ValueError(
                "Tesseract no encontró texto en la imagen. "
                "Comprueba que la imagen tiene buena resolución y el texto es legible."
            )

        log.info("Tesseract OCR: %d caracteres extraídos (lang=%s)", len(text), lang)
        return [text]

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Error procesando imagen con Tesseract: {exc}") from exc


def _available_tesseract_langs() -> set[str]:
    """Devuelve los idiomas instalados en Tesseract."""
    try:
        import pytesseract
        langs = pytesseract.get_languages(config="")
        return set(langs)
    except Exception:
        return {"eng"}


# ── PDF ───────────────────────────────────────────────────────────────────────

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
    n_pages     = len(pages_text)
    full_text   = "\n\n".join(pages_text)
    total_chars = len(full_text)
    if n_pages <= PDF_LONG_PAGES and total_chars <= TEXT_LONG_CHARS:
        return [full_text] if full_text.strip() else [""]
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
    if len(data_rows) <= TABLE_LONG_ROWS:
        all_rows = [header] + data_rows
        return ["\n".join(",".join(r) for r in all_rows)]
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
    total_data_rows = 0
    sheets_data = []
    for sheet in wb.worksheets:
        all_rows  = list(sheet.iter_rows(values_only=True))
        header    = all_rows[0] if all_rows else ()
        data_rows = all_rows[1:] if len(all_rows) > 1 else []
        total_data_rows += len(data_rows)
        sheets_data.append((sheet.title, header, data_rows))
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
    if file_type == "image":
        return False
    return len(chunks) > 1


# ── Guardado en disco ─────────────────────────────────────────────────────────

def save_upload(file_bytes: bytes, file_type: str, conv_id: int,
                upload_folder: str,
                ollama_host: str = "", model: str = "") -> tuple[str, str]:
    base    = str(uuid.uuid4())
    ext_map = {
        "pdf": ".pdf", "docx": ".docx", "txt": ".txt",
        "csv": ".csv", "xlsx": ".xlsx", "image": ".img",
    }
    ext = ext_map.get(file_type, ".bin")

    conv_dir = Path(upload_folder) / str(conv_id)
    conv_dir.mkdir(parents=True, exist_ok=True)
    conv_dir.chmod(0o700)

    orig_path = conv_dir / (base + ext)
    orig_path.write_bytes(file_bytes)
    orig_path.chmod(0o600)

    chunks    = extract_text(file_bytes, file_type,
                             ollama_host=ollama_host, model=model)
    full_text = "\n\n--- [CHUNK BOUNDARY] ---\n\n".join(chunks)
    txt_path  = conv_dir / (base + ".txt")
    txt_path.write_text(full_text, encoding="utf-8")
    txt_path.chmod(0o600)

    return base + ext, str(txt_path)


def get_chunk_range(extracted_text_path: str, from_idx: int,
                    to_idx: int) -> tuple[str, int]:
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


def read_image_base64(extracted_text_path: str) -> str | None:
    """Lee el base64 guardado para una imagen adjunta (no usado con Tesseract)."""
    txt_path = Path(extracted_text_path)
    if not txt_path.exists():
        return None
    content = txt_path.read_text(encoding="utf-8").strip()
    if "--- [CHUNK BOUNDARY] ---" in content:
        content = content.split("--- [CHUNK BOUNDARY] ---")[0].strip()
    return content if content else None
