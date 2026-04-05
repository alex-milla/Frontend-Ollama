"""
Cliente ligero para la API de Ollama.
- Todas las peticiones tienen timeout para no bloquear el servidor.
- No se exponen errores internos al cliente; se logean internamente.
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Generator, Optional

log = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 5   # segundos para conectar
_READ_TIMEOUT    = 60  # segundos para leer (streaming)


def _build_url(host: str, path: str) -> str:
    return host.rstrip("/") + path


# ── Modelos ───────────────────────────────────────────────────────────────────

def list_models(host: str) -> list[dict]:
    """Devuelve lista de modelos disponibles en Ollama. [] si falla."""
    try:
        url = _build_url(host, "/api/tags")
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=_CONNECT_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data.get("models", [])
    except Exception as exc:
        log.warning("list_models falló: %s", exc)
        return []


def ping(host: str) -> bool:
    """True si Ollama responde en el host dado."""
    return len(list_models(host)) >= 0  # 200 aunque no haya modelos


def check_connection(host: str) -> dict:
    """Devuelve {ok, models_count, error?}."""
    try:
        models = list_models(host)
        return {"ok": True, "models_count": len(models)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Chat con streaming ────────────────────────────────────────────────────────

def stream_chat(host: str, model: str, messages: list[dict]) -> Generator[str, None, None]:
    """
    Genera tokens del chat de Ollama vía NDJSON.
    Cada yield es un fragmento de texto o el token especial '[DONE]'.
    """
    url = _build_url(host, "/api/chat")
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=_READ_TIMEOUT) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        yield "[DONE]"
                        return
                except json.JSONDecodeError:
                    continue
    except urllib.error.URLError as exc:
        log.error("stream_chat error de red: %s", exc)
        yield "[ERROR] No se pudo conectar con Ollama."
    except Exception as exc:
        log.error("stream_chat error inesperado: %s", exc)
        yield "[ERROR] Error interno en la conexión con Ollama."
