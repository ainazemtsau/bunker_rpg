from flask import Flask
from .config import DevConfig
from .extensions import cors, socketio
from .sockets import register_socket_events
from bunker.infrastructure.character_randomizer import load_all_character_pools


def create_app(config_object=DevConfig):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # ── extensions ─────────────────────────────────────────────
    cors.init_app(app, resources={r"/*": {"origins": "*"}})
    socketio.init_app(app, cors_allowed_origins="*")

    # ── socket events ──────────────────────────────────────────
    register_socket_events(socketio)
    load_all_character_pools()  # теперь все глобальные переменные заполнены
    return app
