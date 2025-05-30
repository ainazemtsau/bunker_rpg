from __future__ import annotations
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from bunker.core.loader import GameData
from bunker.domain.models.models import Game
from bunker.domain.models.character import Character
from bunker.domain.models.phase2_models import (
    Phase2ActionDef,
    Phase2CrisisDef,
    Phase2Config,
)
from .types import (
    Phase2Action,
    ActionGroup,
    ActionResult,
    CrisisEvent,
    TeamTurnState,
    Phase2ActionType,
    CrisisResult,
)


class Phase2Engine:
    """Движок для Phase2 игры"""

    def __init__(self, game: Game, game_data: GameData, rng: random.Random = None):
        self.game = game
        self.data = game_data
        self.config = game_data.phase2_config
        self.rng = rng or random.Random()

        # Состояние команд
        self._team_states: Dict[str, TeamTurnState] = {}
        self._current_crisis: Optional[CrisisEvent] = None

    def initialize_phase2(self) -> None:
        """Инициализация Phase2"""
        # Настройка базовых параметров из конфига
        settings = self.config.game_settings
        self.game.phase2_bunker_hp = settings.get("starting_bunker_hp", 7)
        self.game.phase2_round = 1
        self.game.phase2_current_team = "outside"

        # Очистка состояний
        self.game.phase2_action_queue.clear()
        self.game.phase2_processed_actions.clear()
        self.game.phase2_current_action_index = 0
        self.game.phase2_action_log.clear()
        self.game.winner = None

        # Инициализация команд
        self._setup_teams()
        self._calculate_team_stats()

    def _setup_teams(self) -> None:
        """Настройка команд для Phase2"""
        bunker_players = list(self.game.team_in_bunker)
        outside_players = list(self.game.team_outside)

        # Убедимся что есть игроки в командах
        if not bunker_players or not outside_players:
            raise ValueError(
                f"Teams must have players! Bunker: {bunker_players}, Outside: {outside_players}"
            )

        self.rng.shuffle(bunker_players)
        self.rng.shuffle(outside_players)

        self._team_states = {
            "bunker": TeamTurnState(
                team_name="bunker",
                players=bunker_players,
                current_player_index=0,
                completed_actions={},
            ),
            "outside": TeamTurnState(
                team_name="outside",
                players=outside_players,
                current_player_index=0,
                completed_actions={},
            ),
        }

        print(f"Teams setup: bunker={bunker_players}, outside={outside_players}")

    def _calculate_team_stats(self) -> None:
        """Расчет характеристик команд"""
        stats = {}

        for team_name, team_state in self._team_states.items():
            team_stats = {"ЗДР": 0, "СИЛ": 0, "ИНТ": 0, "ТЕХ": 0, "ЭМП": 0, "ХАР": 0}

            for player_id in team_state.players:
                if player_id in self.game.characters:
                    char_stats = self.game.characters[player_id].aggregate_stats()
                    for stat, value in char_stats.items():
                        if stat in team_stats:
                            team_stats[stat] += value

            stats[team_name] = team_stats

        self.game.phase2_team_stats = stats

    def get_available_actions(self, team: str) -> List[Phase2ActionDef]:
        """Получить доступные действия для команды"""
        return [
            action
            for action in self.data.phase2_actions.values()
            if action.team == team
        ]

    def get_current_player(self) -> Optional[str]:
        """Получить текущего игрока"""
        current_team = self._team_states.get(self.game.phase2_current_team)
        if not current_team:
            return None

        # Если все игроки уже сделали ход - возвращаем None
        if current_team.current_player_index >= len(current_team.players):
            return None

        return current_team.players[current_team.current_player_index]

    def add_player_action(
        self, player_id: str, action_id: str, params: Dict[str, Any] = None
    ) -> bool:
        """Добавить действие игрока в очередь"""
        current_team = self._team_states.get(self.game.phase2_current_team)
        if not current_team or current_team.get_current_player() != player_id:
            return False

        # Проверяем что действие существует и подходит команде
        action_def = self.data.phase2_actions.get(action_id)
        if not action_def or action_def.team != self.game.phase2_current_team:
            return False

        # Создаем действие
        action = Phase2Action(
            player_id=player_id,
            action_type=Phase2ActionType(action_id),
            params=params or {},
        )

        # Добавляем в состояние команды
        current_team.completed_actions[player_id] = action

        # Группируем с существующими действиями того же типа
        self._update_action_queue(action)

        # Переходим к следующему игроку
        current_team.current_player_index += 1

        return True

    def _update_action_queue(self, new_action: Phase2Action) -> None:
        """Обновить очередь действий, группируя одинаковые"""
        # Ищем существующую группу с таким же действием
        for i, queued_action in enumerate(self.game.phase2_action_queue):
            if queued_action["action_type"] == new_action.action_type.value:
                # Добавляем игрока к существующей группе
                queued_action["participants"].append(new_action.player_id)
                queued_action["params"].update(new_action.params)
                return

        # Создаем новую группу
        self.game.phase2_action_queue.append(
            {
                "action_type": new_action.action_type.value,
                "participants": [new_action.player_id],
                "params": new_action.params,
            }
        )

    def is_team_turn_complete(self) -> bool:
        """Проверить завершен ли ход команды"""
        current_team = self._team_states.get(self.game.phase2_current_team)
        return current_team and current_team.is_complete()

    def can_process_actions(self) -> bool:
        """Можно ли обрабатывать действия (все игроки команды выбрали)"""
        current_team = self._team_states.get(self.game.phase2_current_team)
        if not current_team:
            return False
        # Команда должна завершить ход И должны быть действия для обработки
        return (
            current_team.is_complete()
            and len(self.game.phase2_action_queue) > 0
            and self.game.phase2_current_action_index
            < len(self.game.phase2_action_queue)
        )

    def get_next_action_to_process(self) -> Optional[Dict[str, Any]]:
        """Получить следующее действие для обработки"""
        if self.game.phase2_current_action_index >= len(self.game.phase2_action_queue):
            return None
        return self.game.phase2_action_queue[self.game.phase2_current_action_index]

    def process_current_action(self) -> ActionResult:
        """Обработать текущее действие"""
        if self.game.phase2_current_action_index >= len(self.game.phase2_action_queue):
            raise ValueError("No actions to process")

        action_data = self.game.phase2_action_queue[
            self.game.phase2_current_action_index
        ]
        action_def = self.data.phase2_actions[action_data["action_type"]]

        # Расчет статистик участников
        combined_stats = self._calculate_action_stats(
            action_data["participants"], action_def.stat_weights
        )

        # Бросок кубика
        roll = self.rng.randint(1, 20)
        total = roll + combined_stats
        success = total >= action_def.difficulty

        # Создание результата
        result = ActionResult(
            success=success,
            participants=action_data["participants"],
            action_type=Phase2ActionType(action_data["action_type"]),
            roll_result=roll,
            combined_stats=combined_stats,
            difficulty=action_def.difficulty,
            effects={},
        )

        # Применение эффектов
        if success:
            effects = action_def.effects.get("success", {})
            self._apply_action_effects(effects, result)
        else:
            effects = action_def.effects.get("failure", {})
            self._apply_action_effects(effects, result)

            # Проверка на кризис для команды бункера
            if action_def.team == "bunker" and "crisis_trigger" in effects:
                crisis_id = effects["crisis_trigger"]
                result.crisis_triggered = crisis_id
                self._current_crisis = self._create_crisis_event(crisis_id)

        # Сохраняем результат
        self.game.phase2_processed_actions.append(
            {
                "action_type": action_data["action_type"],
                "participants": action_data["participants"],
                "roll": roll,
                "combined_stats": combined_stats,
                "difficulty": action_def.difficulty,
                "success": success,
                "effects": result.effects,
                "crisis_triggered": result.crisis_triggered,
            }
        )

        self.game.phase2_current_action_index += 1

        return result

    def _calculate_action_stats(
        self, participants: List[str], stat_weights: Dict[str, float]
    ) -> int:
        """Расчет комбинированных характеристик участников"""
        total = 0

        for player_id in participants:
            if player_id in self.game.characters:
                char_stats = self.game.characters[player_id].aggregate_stats()
                for stat, weight in stat_weights.items():
                    total += char_stats.get(stat, 0) * weight

        # Бонус за групповое действие
        if len(participants) > 1:
            group_bonus = self.config.coefficients.get("group_action_bonus", 0.5)
            total += len(participants) * group_bonus

        return int(total)

    def _apply_action_effects(
        self, effects: Dict[str, Any], result: ActionResult
    ) -> None:
        """Применить эффекты действия"""
        result.effects = effects.copy()

        # Урон бункеру
        if "bunker_damage" in effects:
            self.game.phase2_bunker_hp -= effects["bunker_damage"]
            self.game.phase2_bunker_hp = max(0, self.game.phase2_bunker_hp)

        # Лечение бункера
        if "bunker_heal" in effects:
            max_hp = self.config.game_settings.get("starting_bunker_hp", 7)
            self.game.phase2_bunker_hp += effects["bunker_heal"]
            self.game.phase2_bunker_hp = min(max_hp, self.game.phase2_bunker_hp)

    def _create_crisis_event(self, crisis_id: str) -> CrisisEvent:
        """Создать событие кризиса"""
        crisis_def = self.data.phase2_crises.get(crisis_id)
        if not crisis_def:
            raise ValueError(f"Unknown crisis: {crisis_id}")

        # Расчет преимуществ команд
        team_advantages = {}
        threshold = self.config.coefficients.get("stat_advantage_threshold", 5)

        for stat in crisis_def.important_stats:
            bunker_stat = self.game.phase2_team_stats.get("bunker", {}).get(stat, 0)
            outside_stat = self.game.phase2_team_stats.get("outside", {}).get(stat, 0)

            diff = bunker_stat - outside_stat
            if abs(diff) >= threshold:
                if diff > 0:
                    team_advantages["bunker"] = team_advantages.get("bunker", 0) + 1
                else:
                    team_advantages["outside"] = team_advantages.get("outside", 0) + 1

        return CrisisEvent(
            crisis_id=crisis_id,
            name=crisis_def.name,
            description=crisis_def.description,
            important_stats=crisis_def.important_stats,
            team_advantages=team_advantages,
            penalty_on_fail=crisis_def.penalty_on_fail,
        )

    def get_current_crisis(self) -> Optional[CrisisEvent]:
        """Получить текущий кризис"""
        return self._current_crisis

    def resolve_crisis(self, result: CrisisResult) -> None:
        """Разрешить кризис"""
        if not self._current_crisis:
            return

        if result == CrisisResult.BUNKER_LOSE:
            # Применяем штрафы к команде бункера
            for effect, value in self._current_crisis.penalty_on_fail.items():
                if effect == "bunker_damage":
                    self.game.phase2_bunker_hp -= value
                    self.game.phase2_bunker_hp = max(0, self.game.phase2_bunker_hp)

        # Логируем результат кризиса
        self.game.phase2_action_log.append(
            {
                "type": "crisis",
                "crisis_id": self._current_crisis.crisis_id,
                "result": result.value,
                "penalty_applied": result == CrisisResult.BUNKER_LOSE,
            }
        )

        self._current_crisis = None

    def finish_team_turn(self) -> None:
        """Завершить ход команды"""
        current_team = self._team_states.get(self.game.phase2_current_team)
        if not current_team:
            return

        # Логируем ход команды только если были действия
        if self.game.phase2_processed_actions:
            self.game.phase2_action_log.append(
                {
                    "type": "team_turn",
                    "round": self.game.phase2_round,
                    "team": self.game.phase2_current_team,
                    "actions": list(self.game.phase2_processed_actions),
                    "bunker_hp_after": self.game.phase2_bunker_hp,
                }
            )

        # Очищаем состояние для следующего хода
        current_team.completed_actions.clear()
        current_team.current_player_index = 0
        self.game.phase2_action_queue.clear()
        self.game.phase2_processed_actions.clear()
        self.game.phase2_current_action_index = 0

        # Переключаем команду
        if self.game.phase2_current_team == "outside":
            self.game.phase2_current_team = "bunker"
        else:
            self.game.phase2_current_team = "outside"
            self.game.phase2_round += 1

        # Перемешиваем порядок игроков в новой команде
        next_team = self._team_states.get(self.game.phase2_current_team)
        if next_team:
            import random

            random.shuffle(next_team.players)
            next_team.current_player_index = 0  # Сбрасываем индекс

    def check_victory_conditions(self) -> Optional[str]:
        """Проверить условия победы"""
        # Бункер уничтожен
        if self.game.phase2_bunker_hp <= 0:
            self.game.winner = "outside"
            return "bunker_destroyed"

        # Время истекло - победа бункера
        max_rounds = self.config.game_settings.get("max_rounds", 10)
        if self.game.phase2_round > max_rounds:
            self.game.winner = "bunker"
            return "time_limit"

        return None

    def force_setup_teams(
        self, bunker_players: List[str], outside_players: List[str]
    ) -> None:
        """Принудительная установка команд для тестов"""
        if not bunker_players or not outside_players:
            raise ValueError("Both teams must have players")

        self.game.team_in_bunker = set(bunker_players)
        self.game.team_outside = set(outside_players)

        self._team_states = {
            "bunker": TeamTurnState(
                team_name="bunker",
                players=list(bunker_players),
                current_player_index=0,
                completed_actions={},
            ),
            "outside": TeamTurnState(
                team_name="outside",
                players=list(outside_players),
                current_player_index=0,
                completed_actions={},
            ),
        }

        # Пересчитываем статы команд
        self._calculate_team_stats()

        print(f"Force setup teams: bunker={bunker_players}, outside={outside_players}")
