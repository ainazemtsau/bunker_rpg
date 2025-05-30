from datetime import datetime
from flask import request
from flask_socketio import emit, join_room

from ..services.game_service import GameService

service = GameService()
DEFAULT_HOST_NAME = "Host"


# ── helpers ─────────────────────────────────────────────────
def _room_id(snapshot: dict | str) -> str:
    """Принимает либо id-строку, либо snapshot словарь."""
    if isinstance(snapshot, str):
        return f"game:{snapshot}"
    return f"game:{snapshot['id']}"


def _snake(s: str) -> str:
    return s.lower()


# ───────────────── events ──────────────────────────────────
def register_events(sio):
    # ---------- connect / disconnect -----------------------
    @sio.event
    def connect():
        print("[connect]", request.sid)

    @sio.event
    def disconnect():
        snap = service.disconnect(request.sid)
        if snap:
            sio.emit("game_updated", {"game": snap}, room=_room_id(snap))

    # ---------- lobby --------------------------------------
    @sio.on("create_game")
    def create_game(_data):
        snap = service.create_game(DEFAULT_HOST_NAME, request.sid)
        join_room(_room_id(snap))
        emit("game_created", {"game": snap}, room=request.sid)

    @sio.on("join_game")
    def join_game(data):
        try:
            snap, pid = service.join_game(data["id"], data.get("name"), request.sid)
        except ValueError as e:
            return emit("error", {"message": str(e)})

        join_room(_room_id(snap))
        sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
        emit("joined", {"game": snap, "player_id": pid}, room=request.sid)

    @sio.on("rejoin_game")
    def rejoin_game(data):
        try:
            snap = service.rejoin(data["id"], data["player_id"], request.sid)
        except ValueError as e:
            return emit("error", {"message": str(e)})
        join_room(_room_id(snap))
        sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
        emit("rejoined", {"game": snap, "player_id": data["player_id"]})

    # ---------- gameplay -----------------------------------
    @sio.on("game_action")
    def game_action(data):
        try:
            print("[game_action]", data)
            snap = service.execute_game_action(
                data["gameId"], _snake(data["action"]), data.get("payload")
            )
            sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
        except ValueError as e:
            emit("error", {"message": str(e)})

    @sio.on("start_game")
    def start_game(data):
        try:
            snap = service.execute_game_action(
                data["id"], "start_game", {"host_id": data["host_id"]}
            )
        except ValueError as e:
            return emit("error", {"message": str(e)})
        sio.emit("game_started", {"game": snap}, room=_room_id(snap))

    # ---------- misc ---------------------------------------
    @sio.on("host_message")
    def host_message(data):
        gid, msg = data.get("id"), (data.get("message") or "")[:500]
        if not (gid and msg):
            return
        snap = service.rejoin(gid, data["host_id"], request.sid)
        sio.emit(
            "host_announcement",
            {"message": msg, "timestamp": datetime.utcnow().isoformat()},
            room=_room_id(snap),
        )

    @sio.on("player_action")
    def player_action(data):
        gid = data.get("id")
        action = (data.get("action") or "")[:500]
        if not action:
            return
        snap = service.rejoin(gid, data["player_id"], request.sid)
        sio.emit(
            "player_action_received",
            {
                "player_name": data.get("player_name", ""),
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=_room_id(snap),
        )
