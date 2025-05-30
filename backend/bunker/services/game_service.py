from __future__ import annotations
from typing import Dict, Any, Optional

from .repo import game_repo  # In-Memory/SQL repo
from bunker.domain.models.models import Game, Player
from bunker.domain.models.character import Character

# ‼️  Новые пути импорта
from bunker.domain.engine import GameEngine  # сам движок
from bunker.domain.types import ActionType  # enum всех действий


class GameService:
    """Use-case слой: хранит GameEngine-ы и отдаёт фронту их snapshots."""

    def __init__(self) -> None:
        self._engines: dict[str, GameEngine] = {}  # game_id → engine

    # ───────────────── Lobby ────────────────────────────────────────
    def create_game(self, host_name: str, sid: str) -> Dict[str, Any]:
        from pathlib import Path
        from bunker.core.loader import GameData
        from bunker.domain.game_init import GameInitializer

        host = Player(host_name, sid)
        game = Game(host)

        # Create the required dependencies
        data_dir = Path(r"C:/Users/Zema/bunker-game/backend/data")
        game_data = GameData(root=data_dir)
        initializer = GameInitializer(game_data)

        eng = GameEngine(game, initializer)

        self._engines[game.id] = eng
        game_repo.add(game)

        return eng.view()

    def join_game(
        self, gid: str, player_name: str, sid: str
    ) -> tuple[Dict[str, Any], str]:
        game = game_repo.get(gid) or self._not_found()
        player = Player(player_name, sid)
        game.players[player.id] = player
        return self._engines[gid].view(), player.id

    # ───────────────── Gameplay ─────────────────────────────────────
    def execute_game_action(
        self, gid: str, action: str, payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        eng = self._engines.get(gid) or self._not_found()
        try:
            eng.execute(ActionType[action.upper()], payload or {})
        except KeyError:  # неверное имя из фронта
            raise ValueError(f"Unknown action '{action}'")
        return eng.view()

    # ───────────────── Re/connect ───────────────────────────────────
    def rejoin(self, gid: str, player_id: str, sid: str) -> Dict[str, Any]:
        game = game_repo.get(gid) or self._not_found()
        player = game.players.get(player_id) or self._player_not_found()
        player.sid, player.online = sid, True
        return self._engines[gid].view()

    def disconnect(self, sid: str) -> Optional[Dict[str, Any]]:
        for gid, game in game_repo.games.items():
            for p in game.players.values():
                if p.sid == sid:
                    p.online = False
                    return self._engines[gid].view()
        return None

    # ───────────────── Test helper ─────────────────────────────────
    def assign_characters(self, gid: str, templates: list[dict]) -> None:
        """Утилита для юнит-тестов: раздать персонажей."""
        import random

        game = game_repo.get(gid) or self._not_found()
        for pid in game.players:
            game.characters[pid] = Character(**random.choice(templates))

    # ───────────────── Internals ───────────────────────────────────
    @staticmethod
    def _not_found() -> None:
        raise ValueError("Game not found")

    @staticmethod
    def _player_not_found() -> None:
        raise ValueError("Player not found")
