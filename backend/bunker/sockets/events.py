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
            player_id = data.get("player_id") or data.get("playerId")
            if not player_id:
                return emit("error", {"message": "Missing player_id"})
            snap = service.rejoin(data["id"], player_id, request.sid)
        except ValueError as e:
            return emit("error", {"message": str(e)})
        print("[rejoin_game]2", snap)
        join_room(_room_id(snap))
        sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
        emit("rejoined", {"game": snap, "player_id": player_id})

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

    # ---------- Phase2 specific events --------------------
    @sio.on("phase2_player_action")
    def phase2_player_action(data):
        """Игрок выбирает действие в Phase2"""
        try:
            print("[phase2_player_action]", data)
            required_fields = ["gameId", "playerId", "actionId"]
            if not all(field in data for field in required_fields):
                return emit("error", {"message": "Missing required fields"})

            snap = service.execute_game_action(
                data["gameId"],
                "make_action",
                {
                    "player_id": data["playerId"],
                    "action_id": data["actionId"],
                    "params": data.get("params", {}),
                },
            )
            sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
            emit("action_added", {"success": True}, room=request.sid)

        except ValueError as e:
            emit("error", {"message": str(e)})

    @sio.on("phase2_process_action")
    def phase2_process_action(data):
        """Обработать следующее действие в очереди"""
        try:
            print("[phase2_process_action]", data)
            if "gameId" not in data:
                return emit("error", {"message": "Missing gameId"})

            snap = service.execute_game_action(data["gameId"], "process_action", {})
            sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
            emit("action_processed", {"success": True}, room=request.sid)

        except ValueError as e:
            emit("error", {"message": str(e)})

    @sio.on("phase2_resolve_crisis")
    def phase2_resolve_crisis(data):
        """Разрешить кризисную ситуацию"""
        try:
            print("[phase2_resolve_crisis]", data)
            required_fields = ["gameId", "result"]
            if not all(field in data for field in required_fields):
                return emit("error", {"message": "Missing required fields"})

            if data["result"] not in ["bunker_win", "bunker_lose"]:
                return emit("error", {"message": "Invalid crisis result"})

            snap = service.execute_game_action(
                data["gameId"], "resolve_crisis", {"result": data["result"]}
            )
            sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
            emit("crisis_resolved", {"success": True}, room=request.sid)

        except ValueError as e:
            emit("error", {"message": str(e)})

    @sio.on("phase2_finish_turn")
    def phase2_finish_turn(data):
        """Завершить ход команды"""
        try:
            print("[phase2_finish_turn]", data)
            if "gameId" not in data:
                return emit("error", {"message": "Missing gameId"})

            snap = service.execute_game_action(data["gameId"], "finish_team_turn", {})
            sio.emit("game_updated", {"game": snap}, room=_room_id(snap))
            emit("turn_finished", {"success": True}, room=request.sid)

        except ValueError as e:
            emit("error", {"message": str(e)})

    @sio.on("get_phase2_info")
    def get_phase2_info(data):
        """Получить детальную информацию о Phase2"""
        try:
            if "gameId" not in data:
                return emit("error", {"message": "Missing gameId"})

            snap = service.get_game_snapshot(data["gameId"])
            if not snap:
                return emit("error", {"message": "Game not found"})

            # Отправляем только Phase2 данные
            phase2_info = snap.get("phase2", {})
            emit("phase2_info", {"phase2": phase2_info}, room=request.sid)

        except ValueError as e:
            emit("error", {"message": str(e)})

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

    @sio.on("phase2_get_action_preview")
    def phase2_get_action_preview(data):
        """Получить предварительный расчет действия"""
        try:
            print("[phase2_get_action_preview]", data)
            required_fields = ["gameId", "participants", "actionId"]
            if not all(field in data for field in required_fields):
                return emit("error", {"message": "Missing required fields"})

            snap = service.get_game_snapshot(data["gameId"])
            if not snap:
                return emit("error", {"message": "Game not found"})

            # Получаем движок
            eng = service._engines.get(data["gameId"])
            if not eng or not eng._phase2_engine:
                return emit("error", {"message": "Phase2 not available"})

            # Получаем предварительный расчет
            preview = eng._phase2_engine.get_action_preview(
                data["participants"], data["actionId"]
            )

            emit("action_preview", {"preview": preview}, room=request.sid)

        except ValueError as e:
            emit("error", {"message": str(e)})
