"""Bunker Game – resilient backend with reconnection support
========================================================
Key changes compared to the first cut:

* **Stable player‑id tokens** (UUID) that survive refresh or network drops.
* `rejoin_game` event – client presents `game_id` + `player_id`, server re‑binds
  the socket and returns the full game‑state.
* Players hold `online` flag; on `disconnect` we only mark them offline,
  nothing is deleted (clean‑up task could periodically prune).
* Host leaving no longer kills the room instantly – a 60 s grace timer
  (cancelled if host returns). If timer expires the room is closed and
  everyone gets `game_closed`.

This **does not yet persist to a database** but is good enough for
refresh / temporary drop scenarios in LAN.
"""

from __future__ import annotations

import os
import random
import string
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Timer
from typing import Dict, Optional

from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room

# ────────────────────────────────────────────────────────────────────────────────
# Helpers & Models
# ────────────────────────────────────────────────────────────────────────────────


def _gen_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=length))


class Player:
    __slots__ = ("id", "name", "sid", "joined_at", "online")

    def __init__(self, name: str, sid: str):
        self.id: str = uuid.uuid4().hex[:8].upper()
        self.name: str = name
        self.sid: str = sid
        self.joined_at: datetime = datetime.utcnow()
        self.online: bool = True

    # convenience ---------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "online": self.online,
            "joined_at": self.joined_at.isoformat(),
        }


class Game:
    GRACE_PERIOD = 60  # seconds host may stay offline before closing

    def __init__(self, host_sid: str, host_name: str):
        self.id: str = _gen_code()
        self.players: Dict[str, Player] = {}

        host = Player(host_name, host_sid)
        self.players[host.id] = host
        self.host_id: str = host.id

        self.status: str = "waiting"  # waiting | in_progress | finished
        self._host_timer: Optional[Timer] = None

    # ------------------------------------------------------------------ players
    def add_player(self, name: str, sid: str) -> Player:
        player = Player(name, sid)
        self.players[player.id] = player
        return player

    def get_player(self, player_id: str) -> Optional[Player]:
        return self.players.get(player_id)

    def get_by_sid(self, sid: str) -> Optional[Player]:
        for p in self.players.values():
            if p.sid == sid:
                return p
        return None

    def mark_offline(self, sid: str):
        if p := self.get_by_sid(sid):
            p.online = False
            p.sid = ""
            if p.id == self.host_id:
                self._schedule_close()

    def mark_online(self, player: Player, sid: str):
        player.online = True
        player.sid = sid
        if player.id == self.host_id and self._host_timer:
            self._host_timer.cancel()
            self._host_timer = None

    # ----------------------------------------------------------------- helpers
    def is_empty(self) -> bool:
        return not any(p.online for p in self.players.values())

    def _schedule_close(self):
        if self._host_timer:
            return

        def _close():
            emit("game_closed", room=self.id)
            registry.remove(self.id)
            print(f"[close] Game {self.id} closed (host absent)")

        self._host_timer = Timer(self.GRACE_PERIOD, _close)
        self._host_timer.start()

    # ------------------------------------------------------------------ serialize
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "host_id": self.host_id,
            "players": [p.to_dict() for p in self.players.values()],
        }


class GameRegistry:
    def __init__(self):
        self._games: Dict[str, Game] = {}

    # CRUD ---------------------------------------------------------------
    def create(self, host_sid: str, host_name: str) -> Game:
        game = Game(host_sid, host_name)
        self._games[game.id] = game
        return game

    def get(self, gid: str) -> Optional[Game]:
        return self._games.get(gid)

    def remove(self, gid: str):
        self._games.pop(gid, None)

    # -------------------------------------------------------------------
    def player_by_sid(self, sid: str) -> Optional[tuple[Game, Player]]:
        for g in self._games.values():
            if p := g.get_by_sid(sid):
                return g, p
        return None


registry = GameRegistry()

# ────────────────────────────────────────────────────────────────────────────────
# Flask / SocketIO setup
# ────────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "super-secret")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ────────────────────────────────────────────────────────────────────────────────
# SocketIO events
# ────────────────────────────────────────────────────────────────────────────────


@socketio.event
def connect():
    print("[connect]", request.sid)


@socketio.event
def disconnect():
    print("[disconnect]", request.sid)
    gp = registry.player_by_sid(request.sid)
    if not gp:
        return
    game, player = gp
    game.mark_offline(request.sid)
    emit("player_list", game.to_dict(), room=game.id)


# ─────────────────────────────── create / join / rejoin ─────────────────────────


@socketio.on("create_game")
def create_game(data):
    name = data.get("name", "Host")
    game = registry.create(request.sid, name)
    join_room(game.id)

    emit(
        "game_created",
        {
            "game": game.to_dict(),  # новая схема
            "game_id": game.id,  # ← legacy alias
            "player_id": game.host_id,
            "host_id": game.host_id,  # ← legacy alias
        },
    )
    emit("player_list", game.to_dict(), room=game.id)


@socketio.on("join_game")
def join_game(data):
    gid = str(data.get("id", "")).upper()
    name = data.get("name", "Player")

    if not (game := registry.get(gid)):
        emit("error", {"message": "Game not found"})
        return

    player = game.add_player(name, request.sid)
    join_room(game.id)

    emit("joined", {"game": game.to_dict(), "player_id": player.id})
    emit("player_list", game.to_dict(), room=game.id)


@socketio.on("rejoin_game")
def rejoin_game(data):
    gid = data.get("id")
    pid = data.get("player_id")

    if not (game := registry.get(gid)):
        emit("error", {"message": "Game not found"})
        return
    player = game.get_player(pid)
    if not player:
        emit("error", {"message": "Player not recognised"})
        return

    game.mark_online(player, request.sid)
    join_room(game.id)

    emit("rejoined", {"game": game.to_dict(), "player_id": player.id})
    emit("player_list", game.to_dict(), room=game.id)


# ─────────────────────────── game control events (minimal) ──────────────────────


@socketio.on("start_game")
def start_game(data):
    gid = data.get("id")
    if not (game := registry.get(gid)):
        emit("error", {"message": "Game not found"})
        return
    if game.host_id != registry.player_by_sid(request.sid)[1].id:
        emit("error", {"message": "Only host can start"})
        return

    game.status = "in_progress"
    emit("game_started", {"status": game.status}, room=game.id)


@socketio.on("host_message")
def host_message(data):
    gid = data.get("id")
    message = data.get("message", "")[:500]
    if not message:
        return
    if not (game := registry.get(gid)):
        return
    emit(
        "host_announcement",
        {"message": message, "timestamp": datetime.utcnow().isoformat()},
        room=game.id,
    )


@socketio.on("player_action")
def player_action(data):
    gid = data.get("id")
    action = data.get("action", "")[:500]
    if not action:
        return
    if not (game := registry.get(gid)):
        return
    gp = registry.player_by_sid(request.sid)
    if not gp:
        return
    _, player = gp
    payload = {
        "player": player.name,
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
    }
    # log for host only
    emit("player_action_received", payload, room=game.id)


# ────────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
