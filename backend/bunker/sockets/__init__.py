from flask_socketio import SocketIO
from .events import register_events


def register_socket_events(socketio: SocketIO):
    register_events(socketio)
