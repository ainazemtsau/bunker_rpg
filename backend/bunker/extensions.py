from flask_cors import CORS
from flask_socketio import SocketIO

cors = CORS()
# async_mode = 'eventlet' (по‑умолчанию)
socketio = SocketIO(async_mode="eventlet")
