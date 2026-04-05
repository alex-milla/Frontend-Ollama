import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_env_file = BASE_DIR / "config.env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


class Config:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")
    if not SECRET_KEY or SECRET_KEY == "cambiar-esto-por-un-valor-aleatorio-seguro":
        import secrets
        SECRET_KEY = secrets.token_hex(32)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = 86400 * 7

    DB_PATH: str = os.environ.get(
        "DB_PATH",
        str(BASE_DIR / "data" / "ollama-chat.db"),
    )

    OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://192.168.1.100:11434")

    UPLOAD_FOLDER: str = os.environ.get(
        "UPLOAD_FOLDER",
        str(BASE_DIR / "data" / "uploads"),
    )

    OUTPUT_FOLDER: str = os.environ.get(
        "OUTPUT_FOLDER",
        str(BASE_DIR / "data" / "outputs"),
    )

    MAX_CONTENT_LENGTH: int = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
