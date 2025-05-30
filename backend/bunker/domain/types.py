# bunker/domain/types.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol


class GamePhase(Enum):
    LOBBY = auto()
    BUNKER = auto()
    REVEAL = auto()
    DISCUSSION = auto()
    VOTING = auto()
    PHASE2 = auto()
    FINISHED = auto()


class ActionType(Enum):
    START_GAME = auto()
    OPEN_BUNKER = auto()
    REVEAL = auto()
    END_DISCUSSION = auto()
    CAST_VOTE = auto()
    REVEAL_RESULTS = auto()
    MAKE_ACTION = auto()
    PROCESS_ACTION = auto()  # новое
    RESOLVE_CRISIS = auto()  # новое
    FINISH_TEAM_TURN = auto()  # новое


@dataclass(frozen=True)
class GameAction:
    type: ActionType
    player_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class SkillCheck:
    skill_name: str
    base_difficulty: int
    required_roll: int
    modifiers: Dict[str, int]


@dataclass(frozen=True)
class ActionResult:
    success: bool
    critical_failure: bool = False
    crisis_triggered: Optional[str] = None
    effects: Dict[str, Any] = None


class GameEvent(Protocol):
    """Интерфейс для событий в игре"""

    def get_type(self) -> str: ...
    def get_data(self) -> Dict[str, Any]: ...


class EventHandler(Protocol):
    """Интерфейс для обработчиков событий"""

    def can_handle(self, event: GameEvent) -> bool: ...
    def handle(self, event: GameEvent, game_state: Any) -> None: ...
