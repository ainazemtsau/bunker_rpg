# bunker/domain/engine/legacy_adapter.py
from __future__ import annotations
from typing import Any, Dict, Optional
from enum import Enum, auto

from bunker.domain.types import GamePhase, ActionType, GameAction
from bunker.domain.engine import GameEngine as NewGameEngine
from bunker.domain.phase2.actions import (
    ActionRegistry,
    AttackBunkerAction,
    RepairBunkerAction,
)


# Enum для обратной совместимости
class Phase(Enum):
    LOBBY = auto()
    BUNKER = auto()
    REVEAL = auto()
    DISCUSSION = auto()
    VOTING = auto()
    PHASE2 = auto()
    FINISHED = auto()


class Action(Enum):
    START_GAME = auto()
    OPEN_BUNKER = auto()
    REVEAL = auto()
    END_DISCUSSION = auto()
    CAST_VOTE = auto()
    REVEAL_RESULTS = auto()
    MAKE_ACTION = auto()


class GameEngine:
    """Адаптер для обратной совместимости со старым API"""

    def __init__(self, game, initializer=None):
        from bunker.domain.game_init import GameInitializer
        from bunker.core.loader import GameData
        from pathlib import Path

        # Создаем недостающие зависимости если не переданы
        if initializer is None:
            data_dir = Path(r"C:/Users/Zema/bunker-game/backend/data")
            game_data = GameData(root=data_dir)
            initializer = GameInitializer(game_data)

        # Создаем реестр действий
        action_registry = ActionRegistry()
        action_registry.register_action(AttackBunkerAction())
        action_registry.register_action(RepairBunkerAction())

        self._engine = NewGameEngine(game, initializer, action_registry)
        self.game = game

    @property
    def phase(self) -> Phase:
        """Маппинг новых фаз в старые"""
        phase_mapping = {
            GamePhase.LOBBY: Phase.LOBBY,
            GamePhase.BUNKER: Phase.BUNKER,
            GamePhase.REVEAL: Phase.REVEAL,
            GamePhase.DISCUSSION: Phase.DISCUSSION,
            GamePhase.VOTING: Phase.VOTING,
            GamePhase.PHASE2: Phase.PHASE2,
            GamePhase.FINISHED: Phase.FINISHED,
        }
        return phase_mapping[self._engine._phase]

    def execute(self, action: Action, payload: Optional[Dict[str, Any]] = None) -> None:
        """Адаптер для старого API execute"""
        # Маппинг старых действий в новые
        action_mapping = {
            Action.START_GAME: ActionType.START_GAME,
            Action.OPEN_BUNKER: ActionType.OPEN_BUNKER,
            Action.REVEAL: ActionType.REVEAL,
            Action.END_DISCUSSION: ActionType.END_DISCUSSION,
            Action.CAST_VOTE: ActionType.CAST_VOTE,
            Action.REVEAL_RESULTS: ActionType.REVEAL_RESULTS,
            Action.MAKE_ACTION: ActionType.MAKE_ACTION,
        }

        new_action_type = action_mapping[action]
        player_id = payload.get("player_id") if payload else None

        game_action = GameAction(
            type=new_action_type, player_id=player_id, payload=payload
        )

        self._engine.execute(game_action)

    def view(self) -> Dict[str, Any]:
        """Прокси к новому методу view"""
        return self._engine.view()
