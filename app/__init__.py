"""
Factory de la aplicación Flask.
Se importa desde Gunicorn y desde los tests.
"""
import logging
from flask import Flask

from .config import Config
from .database import init_db


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    # Logging básico
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # Inicializa la base de datos (crea tablas si no existen)
    init_db(app.config["DB_PATH"])

    # Registrar blueprints
    from .auth  import bp as auth_bp
    from .chat  import bp as chat_bp
    from .admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)

    return app
