# bunker/domain/engine/game_engine.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import Counter

from bunker.domain.types import GamePhase, ActionType, GameAction
from bunker.domain.events import EventBus, BaseGameEvent
from bunker.domain.phase2.actions import (
    ActionRegistry,
    AttackBunkerAction,
    RepairBunkerAction,
)
from bunker.domain.phase2.team_manager import TeamManager
from bunker.domain.phase2.turn_processor import TurnProcessor


class GameEngine:
    """Основной движок игры"""

    def __init__(self, game, initializer, action_registry: ActionRegistry = None):
        self.game = game
        self._initializer = initializer
        self._phase = GamePhase.LOBBY
        self._event_bus = EventBus()
        self._action_registry = action_registry or self._create_default_registry()
        self._team_manager = TeamManager()
        self._turn_processor = TurnProcessor(self._action_registry, self._event_bus)

        # Phase2 состояние
        self._bunker_team = None
        self._outside_team = None
        self._current_team = None

        # Настройки Phase2
        self.PHASE2_MAX_ROUNDS = 10
        self.PHASE2_BUNKER_HP = 7

    def execute(self, action: GameAction) -> None:
        """Выполнить игровое действие"""
        if not self._can_execute_action(action):
            raise ValueError(f"Cannot execute {action.type} in {self._phase}")

        # Диспетчеризация по фазам
        if self._phase in (
            GamePhase.LOBBY,
            GamePhase.BUNKER,
            GamePhase.REVEAL,
            GamePhase.DISCUSSION,
            GamePhase.VOTING,
        ):
            self._execute_phase1_action(action)
        elif self._phase == GamePhase.PHASE2:
            self._execute_phase2_action(action)

    def view(self) -> Dict[str, Any]:
        """Получить представление игры"""
        data = self.game.to_dict()
        data["phase"] = self._phase.name.lower()
        data["available_actions"] = self._get_available_actions()

        # Phase1 специфичные поля
        if self._phase in (GamePhase.REVEAL, GamePhase.DISCUSSION, GamePhase.VOTING):
            data["current_turn"] = self._get_current_turn_info()

        if self._phase == GamePhase.VOTING:
            data["voting_status"] = {
                "voted": len(self.game.votes),
                "total": len(self.game.alive_ids()),
            }

        # Phase2 специфичные поля
        if self._phase in (GamePhase.PHASE2, GamePhase.FINISHED):
            data.update(self._get_phase2_view())

        return data

    def _execute_phase1_action(self, action: GameAction) -> None:
        """Выполнить действие Phase1"""
        if action.type == ActionType.START_GAME:
            self._start_game()
        elif action.type == ActionType.OPEN_BUNKER:
            self._open_bunker()
        elif action.type == ActionType.REVEAL:
            self._reveal_next(action.payload)
        elif action.type == ActionType.END_DISCUSSION:
            self._end_discussion()
        elif action.type == ActionType.CAST_VOTE:
            self._cast_vote(action.payload)
        elif action.type == ActionType.REVEAL_RESULTS:
            self._reveal_results()

    def _execute_phase2_action(self, action: GameAction) -> None:
        """Выполнить действие Phase2"""
        if action.type == ActionType.MAKE_ACTION:
            self._phase2_player_action(action.payload)

    # ======== Phase1 методы ========
    def _start_game(self):
        self.game.shuffle_turn_order()
        self.game.attr_index = 0
        self.game.status = "in_progress"
        self._initializer.setup_new_game(self.game)
        self._phase = GamePhase.BUNKER

    def _open_bunker(self):
        if self.game.bunker_reveal_idx >= len(self.game.bunker_cards):
            raise ValueError("Все карты открыты")

        card = self.game.bunker_cards[self.game.bunker_reveal_idx]
        from dataclasses import asdict, is_dataclass

        self.game.revealed_bunker_cards.append(
            asdict(card) if is_dataclass(card) else dict(card)
        )
        self.game.bunker_reveal_idx += 1

        self.game.shuffle_turn_order()
        self._phase = GamePhase.REVEAL

    def _reveal_next(self, payload: Dict[str, Any]):
        pid, attr = payload["player_id"], payload["attribute"]
        expected, allowed = self._get_current_turn_info()
        if pid != expected["player_id"] or attr not in expected["allowed"]:
            raise ValueError("Invalid reveal")

        self.game.characters[pid].reveal(attr)
        if self._is_last_player():
            self.game.attr_index += 1
            self._phase = GamePhase.DISCUSSION
        else:
            self.game.current_idx += 1

    def _end_discussion(self):
        if self.game.attr_index == 1:
            self._phase = GamePhase.BUNKER
        else:
            self._phase = GamePhase.VOTING
            self.game.votes.clear()

    def _cast_vote(self, payload: Dict[str, Any]):
        self.game.votes[payload["voter_id"]] = payload["target_id"]

    def _reveal_results(self):
        target = Counter(self.game.votes.values()).most_common(1)[0][0]
        self.game.eliminated_ids.add(target)
        self.game.votes.clear()
        self.game.shuffle_turn_order()

        # Проверяем переход к Phase2
        if (
            len(self.game.alive_ids()) <= len(self.game.eliminated_ids)
            or self.game.attr_index >= 7
        ):
            self._init_phase2()
        else:
            self._phase = GamePhase.BUNKER

    # ======== Phase2 методы ========
    def _init_phase2(self):
        """Инициализация Phase2"""
        alive = set(self.game.alive_ids())
        eliminated = set(self.game.eliminated_ids)

        self._bunker_team, self._outside_team = self._team_manager.initialize_teams(
            alive, eliminated
        )

        # Обновляем состояние игры
        self.game.team_in_bunker = alive
        self.game.team_outside = eliminated
        self.game.phase2_round = 1
        self.game.phase2_bunker_hp = self.PHASE2_BUNKER_HP
        self.game.phase2_action_log = []
        self.game.winner = None

        # Начинаем с команды outside
        self._current_team = self._outside_team
        self.game.phase2_team = "outside"
        self._update_game_turn_order()

        self._phase = GamePhase.PHASE2

    def _phase2_player_action(self, payload: Dict[str, Any]):
        """Обработка действия игрока в Phase2"""
        if self.game.winner:
            self._phase = GamePhase.FINISHED
            return

        player_id = payload["player_id"]
        current_player = self._team_manager.get_current_player(self._current_team)

        if player_id != current_player:
            raise ValueError("Not this player's turn")

        # Выполняем действие (упрощенная версия для совместимости)
        action_type = payload.get("action_type", "noop")
        self._current_team.completed_actions[player_id] = {
            "player_id": player_id,
            "action_type": action_type,
            "params": payload.get("params", {}),
            "result": "success",
        }

        # Переходим к следующему игроку
        team_finished = self._team_manager.advance_turn(self._current_team)

        if team_finished:
            self._finish_team_turn()
        else:
            self._update_game_turn_order()

    def _finish_team_turn(self):
        """Завершить ход команды"""
        team_name = self.game.phase2_team
        actions = list(self._current_team.completed_actions.values())

        # Подсчитываем урон (упрощенная логика)
        damage = 0
        if team_name == "outside":
            damage = len([a for a in actions if a["action_type"] == "attack"])
            self.game.phase2_bunker_hp -= damage

        # Логируем
        self.game.phase2_action_log.append(
            {
                "round": self.game.phase2_round,
                "team": team_name,
                "actions": actions,
                "damage": damage,
                "bunker_hp_after": self.game.phase2_bunker_hp,
            }
        )

        # Проверяем победителя
        self._check_winner()
        if self.game.winner:
            self._phase = GamePhase.FINISHED
            return

        # Переключаем команду
        if team_name == "outside":
            self._current_team = self._bunker_team
            self.game.phase2_team = "bunker"
        else:
            self._current_team = self._outside_team
            self.game.phase2_team = "outside"
            self.game.phase2_round += 1

        # Сбрасываем ход команды
        self._team_manager.reset_team_turn(self._current_team)
        self._update_game_turn_order()

    def _check_winner(self):
        """Проверить условия победы"""
        if self.game.phase2_bunker_hp <= 0:
            self.game.winner = "outside"
        elif (
            self.game.phase2_round > self.PHASE2_MAX_ROUNDS
            and self.game.phase2_team == "outside"
        ):
            self.game.winner = "bunker"

    # ======== Вспомогательные методы ========
    def _get_current_turn_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем ходе"""
        if self._phase == GamePhase.REVEAL:
            pid = self.game.turn_order[self.game.current_idx]
            char = self.game.characters[pid]
            if self.game.attr_index == 0:
                allowed = [self.game.first_round_attribute]
            else:
                allowed = [a for a in char.reveal_order if not char.is_revealed(a)]
            return {"player_id": pid, "allowed": allowed}
        return {}

    def _update_game_turn_order(self):
        """Обновить порядок ходов в game объекте для совместимости"""
        if self._current_team:
            self.game.phase2_turn_order = self._current_team.turn_order
            self.game.phase2_current_idx = self._current_team.current_player_index

    def _get_phase2_view(self) -> Dict[str, Any]:
        """Получить представление Phase2"""
        return {
            "phase2": {
                "round": getattr(self.game, "phase2_round", 1),
                "team": getattr(self.game, "phase2_team", "outside"),
                "bunker_hp": getattr(
                    self.game, "phase2_bunker_hp", self.PHASE2_BUNKER_HP
                ),
                "turn_order": getattr(self.game, "phase2_turn_order", []),
                "current_idx": getattr(self.game, "phase2_current_idx", 0),
                "current_player": (
                    self.game.phase2_turn_order[self.game.phase2_current_idx]
                    if hasattr(self.game, "phase2_turn_order")
                    and self.game.phase2_turn_order
                    and self.game.phase2_current_idx < len(self.game.phase2_turn_order)
                    else None
                ),
                "action_log": getattr(self.game, "phase2_action_log", []),
                "winner": getattr(self.game, "winner", None),
            }
        }

    def _is_last_player(self) -> bool:
        return self.game.current_idx >= len(self.game.turn_order) - 1

    def _can_execute_action(self, action: GameAction) -> bool:
        """Проверить можно ли выполнить действие"""
        available = self._get_available_actions()
        return action.type.name.lower() in available

    def _get_available_actions(self) -> List[str]:
        """Получить доступные действия"""
        if self._phase == GamePhase.LOBBY:
            return ["start_game"]
        elif self._phase == GamePhase.BUNKER:
            return ["open_bunker"]
        elif self._phase == GamePhase.REVEAL:
            return ["reveal"]
        elif self._phase == GamePhase.DISCUSSION:
            return ["end_discussion"]
        elif self._phase == GamePhase.VOTING:
            if len(self.game.votes) >= len(self.game.alive_ids()):
                return ["reveal_results"]
            else:
                return ["cast_vote"]
        elif self._phase == GamePhase.PHASE2:
            return ["make_action"]
        else:
            return []

    def _create_default_registry(self) -> ActionRegistry:
        """Создать стандартный реестр действий"""
        registry = ActionRegistry()
        registry.register_action(AttackBunkerAction())
        registry.register_action(RepairBunkerAction())
        return registry
