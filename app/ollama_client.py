"""
Cliente ligero para la API de Ollama.
"""
import json
import logging
import urllib.request
import urllib.error
from typing import Generator, Optional

log = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 5
_READ_TIMEOUT    = 60


def _build_url(host: str, path: str) -> str:
    return host.rstrip("/") + path


def list_models(host: str) -> list[dict]:
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
    return len(list_models(host)) >= 0


def check_connection(host: str) -> dict:
    try:
        models = list_models(host)
        return {"ok": True, "models_count": len(models)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def stream_chat(host: str, model: str, messages: list[dict]) -> Generator[str, None, None]:
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
