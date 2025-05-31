from __future__ import annotations
from typing import Dict, Any, Optional
from pathlib import Path

from .repo import game_repo
from bunker.domain.models.models import Game, Player
from bunker.domain.engine import GameEngine
from bunker.domain.types import ActionType
from bunker.core.loader import GameData
from bunker.domain.game_init import GameInitializer


class GameService:
    """Use-case слой: хранит GameEngine-ы и отдаёт фронту их snapshots."""

    def __init__(self) -> None:
        self._engines: dict[str, GameEngine] = {}

        # Загружаем данные один раз
        data_dir = Path(r"C:/Users/Zema/bunker-game/backend/data")
        self._game_data = GameData(root=data_dir)
        self._initializer = GameInitializer(self._game_data)

    # ───────────────── Lobby ────────────────────────────────────────
    def create_game(self, host_name: str, sid: str) -> Dict[str, Any]:
        host = Player(host_name, sid)
        game = Game(host)

        # Создаем движок с данными
        eng = GameEngine(game, self._initializer, self._game_data)

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
            action_type = ActionType[action.upper()]
            from bunker.domain.types import GameAction

            game_action = GameAction(type=action_type, payload=payload or {})
            eng.execute(game_action)
        except KeyError:
            raise ValueError(f"Unknown action '{action}'")
        return eng.view()

    def get_game_snapshot(self, gid: str) -> Optional[Dict[str, Any]]:
        """Получить снимок игры без выполнения действий"""
        eng = self._engines.get(gid)
        if not eng:
            return None
        return eng.view()

    def get_phase2_available_actions(self, gid: str, team: str) -> List[Dict[str, Any]]:
        """Получить доступные действия для команды в Phase2"""
        eng = self._engines.get(gid) or self._not_found()
        if not eng._phase2_engine:
            return []

        actions = eng._phase2_engine.get_available_actions(team)
        return [
            {
                "id": action.id,
                "name": action.name,
                "difficulty": action.difficulty,
                "required_stats": action.required_stats,
                "stat_weights": action.stat_weights,
            }
            for action in actions
        ]

    def get_phase2_team_stats(self, gid: str) -> Dict[str, Dict[str, int]]:
        """Получить статистики команд"""
        eng = self._engines.get(gid) or self._not_found()
        game = eng.game
        return game.phase2_team_stats

    # ───────────────── Re/connect ───────────────────────────────────
    def rejoin(self, gid: str, player_id: str, sid: str) -> Dict[str, Any]:
        game = game_repo.get(gid) or self._not_found()
        player = game.players.get(player_id)
        if not player and getattr(game, "host", None) and game.host.id == player_id:
            print(f"Found host")
            player = game.host
        if not player:
            print(f"NotFound player")
            self._player_not_found()

        player.sid, player.online = sid, True
        return self._engines[gid].view()

    def disconnect(self, sid: str) -> Optional[Dict[str, Any]]:
        for gid, game in game_repo.games.items():
            for p in game.players.values():
                if p.sid == sid:
                    p.online = False
                    return self._engines[gid].view()
        return None

    # ───────────────── Internals ───────────────────────────────────
    @staticmethod
    def _not_found() -> None:
        raise ValueError("Game not found")

    @staticmethod
    def _player_not_found() -> None:
        raise ValueError("Player not found")
