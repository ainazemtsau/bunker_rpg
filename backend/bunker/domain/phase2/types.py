from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum


Phase2ActionType = str


class CrisisResult(Enum):
    BUNKER_WIN = "bunker_win"
    BUNKER_LOSE = "bunker_lose"


@dataclass
class Phase2Action:
    """Действие игрока в Phase2"""

    player_id: str
    action_type: Phase2ActionType
    params: Dict[str, Any]


@dataclass
class ActionGroup:
    """Группа игроков выполняющих одинаковое действие"""

    action_type: Phase2ActionType
    participants: List[str]
    combined_stats: Dict[str, int]
    difficulty: int
    params: Dict[str, Any]


@dataclass
class ActionResult:
    """Результат выполнения действия"""

    success: bool
    participants: List[str]
    action_type: Phase2ActionType
    roll_result: int
    combined_stats: int
    difficulty: int
    effects: Dict[str, Any]
    crisis_triggered: Optional[str] = None


@dataclass
class MiniGameInfo:
    """Информация о мини-игре для кризиса"""

    mini_game_id: str
    name: str
    rules: str


@dataclass
class CrisisEvent:
    """Кризисная ситуация с мини-игрой"""

    crisis_id: str
    name: str
    description: str
    important_stats: List[str]
    team_advantages: Dict[str, int]
    penalty_on_fail: Dict[str, Any]
    mini_game: Optional[MiniGameInfo] = None  # выбранная мини-игра


@dataclass
class TeamTurnState:
    """Состояние хода команды"""

    team_name: str
    players: List[str]
    current_player_index: int
    completed_actions: Dict[str, Phase2Action]

    def get_current_player(self) -> Optional[str]:
        if self.current_player_index >= len(self.players):
            return None
        return self.players[self.current_player_index]

    def is_complete(self) -> bool:
        return len(self.completed_actions) == len(self.players)
