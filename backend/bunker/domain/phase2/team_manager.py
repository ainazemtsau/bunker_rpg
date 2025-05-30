# bunker/domain/phase2/team_manager.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Set
import random


@dataclass
class TeamState:
    """Состояние команды"""

    members: Set[str]
    turn_order: List[str]
    current_player_index: int
    completed_actions: dict  # player_id -> action_result


class TeamManager:
    """Управление командами в Phase2"""

    def __init__(self, rng=None):
        self._rng = rng or random.Random()

    def initialize_teams(
        self, alive_players: Set[str], eliminated_players: Set[str]
    ) -> tuple[TeamState, TeamState]:
        """Инициализировать команды для Phase2"""
        bunker_team = TeamState(
            members=alive_players,
            turn_order=list(alive_players),
            current_player_index=0,
            completed_actions={},
        )

        outside_team = TeamState(
            members=eliminated_players,
            turn_order=list(eliminated_players),
            current_player_index=0,
            completed_actions={},
        )

        # Перемешиваем порядок ходов
        self._rng.shuffle(bunker_team.turn_order)
        self._rng.shuffle(outside_team.turn_order)

        return bunker_team, outside_team

    def get_current_player(self, team: TeamState) -> str:
        """Получить текущего игрока команды"""
        if team.current_player_index >= len(team.turn_order):
            raise ValueError("All players have completed their turns")
        return team.turn_order[team.current_player_index]

    def advance_turn(self, team: TeamState) -> bool:
        """Продвинуть ход в команде. Возвращает True если команда завершила раунд"""
        team.current_player_index += 1
        return team.current_player_index >= len(team.turn_order)

    def reset_team_turn(self, team: TeamState) -> None:
        """Сбросить ход команды для нового раунда"""
        team.current_player_index = 0
        team.completed_actions.clear()
        self._rng.shuffle(team.turn_order)
