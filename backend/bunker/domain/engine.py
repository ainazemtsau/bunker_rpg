# bunker/domain/engine/game_engine.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import Counter

from bunker.domain.types import GamePhase, ActionType, GameAction
from bunker.domain.phase2.phase2_engine import Phase2Engine
from bunker.domain.phase2.types import CrisisResult
from bunker.core.loader import GameData


class GameEngine:
    """Основной движок игры"""

    def __init__(self, game, initializer, game_data: GameData = None):
        self.game = game
        self._initializer = initializer
        self._phase = GamePhase.LOBBY
        self._game_data = game_data

        # Phase2 engine
        self._phase2_engine: Optional[Phase2Engine] = None

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
        if not self._phase2_engine:
            raise ValueError("Phase2 engine not initialized")

        print(f"\n=== Executing Phase2 action: {action.type} ===")

        if action.type == ActionType.MAKE_ACTION:
            self._phase2_player_action(action.payload)
        elif action.type == ActionType.PROCESS_ACTION:
            self._phase2_process_action()
        elif action.type == ActionType.RESOLVE_CRISIS:
            self._phase2_resolve_crisis(action.payload)
        elif action.type == ActionType.FINISH_TEAM_TURN:
            self._phase2_finish_team_turn()

        # ВАЖНО: Проверяем победу после КАЖДОГО действия
        print("Checking victory conditions after action...")
        self._check_phase2_victory()

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
        current_turn_info = self._get_current_turn_info()
        if (
            pid != current_turn_info["player_id"]
            or attr not in current_turn_info["allowed"]
        ):
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
        if not self._game_data:
            raise ValueError("GameData required for Phase2")

        # Проверяем есть ли уже установленные команды (для тестов)
        if not self.game.team_in_bunker and not self.game.team_outside:
            # Распределяем игроков по командам автоматически
            alive = set(self.game.alive_ids())
            eliminated = set(self.game.eliminated_ids)

            self.game.team_in_bunker = alive
            self.game.team_outside = eliminated

        print(
            f"Phase2 teams - Bunker: {list(self.game.team_in_bunker)}, Outside: {list(self.game.team_outside)}"
        )

        # Инициализируем движок Phase2
        self._phase2_engine = Phase2Engine(self.game, self._game_data)
        self._phase2_engine.initialize_phase2()

        self._phase = GamePhase.PHASE2

    def _phase2_player_action(self, payload: Dict[str, Any]):
        """Добавить действие игрока в Phase2"""
        if not self._phase2_engine:
            return

        player_id = payload["player_id"]
        action_id = payload["action_id"]
        params = payload.get("params", {})

        success = self._phase2_engine.add_player_action(player_id, action_id, params)
        if not success:
            raise ValueError("Invalid player action")

        # Проверяем завершение игры после каждого действия
        self._check_phase2_victory()

    def _phase2_process_action(self):
        """Обработать следующее действие в очереди"""
        if not self._phase2_engine:
            return

        if not self._phase2_engine.can_process_actions():
            raise ValueError("Cannot process actions yet")

        result = self._phase2_engine.process_current_action()

        # Проверяем завершение игры
        self._check_phase2_victory()

        return result

    def _phase2_resolve_crisis(self, payload: Dict[str, Any]):
        """Разрешить кризис"""
        if not self._phase2_engine:
            return

        result_str = payload.get("result")
        if result_str not in ["bunker_win", "bunker_lose"]:
            raise ValueError("Invalid crisis result")

        result = CrisisResult(result_str)
        self._phase2_engine.resolve_crisis(result)

        # Проверяем завершение игры
        self._check_phase2_victory()

    def _phase2_finish_team_turn(self):
        """Завершить ход команды"""
        if not self._phase2_engine:
            return

        self._phase2_engine.finish_team_turn()

        # Проверяем завершение игры
        self._check_phase2_victory()

    def _check_phase2_victory(self):
        """Проверить условия победы в Phase2"""
        if not self._phase2_engine:
            return

        print(f"Current phase before victory check: {self._phase}")
        victory_condition = self._phase2_engine.check_victory_conditions()

        if victory_condition:
            print(
                f"VICTORY CONDITION MET: {victory_condition}, winner: {self.game.winner}"
            )
            print(f"Changing phase from {self._phase} to FINISHED")
            self._phase = GamePhase.FINISHED
        else:
            print("No victory condition met, continuing game...")

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

    def _get_phase2_view(self) -> Dict[str, Any]:
        """Получить представление Phase2 С ДЕТАЛЬНОЙ ИСТОРИЕЙ"""
        if not self._phase2_engine:
            return {"phase2": {}}

        current_player = self._phase2_engine.get_current_player()
        available_actions = []

        # Получаем доступные действия
        if current_player:
            actions = self._phase2_engine.get_available_actions_for_player(
                current_player
            )
            for action in actions:
                status_mods = self._phase2_engine._status_manager.get_action_modifiers(
                    action.id
                )

                action_data = {
                    "id": action.id,
                    "name": action.name,
                    "difficulty": action.difficulty,
                    "stat_weights": action.stat_weights,
                }

                if status_mods["blocked"]:
                    action_data["blocked"] = True
                    action_data["blocking_statuses"] = status_mods["blocking_statuses"]
                elif status_mods["difficulty_modifier"] != 0:
                    action_data["modified_difficulty"] = (
                        action.difficulty + status_mods["difficulty_modifier"]
                    )
                    action_data["difficulty_modifier"] = status_mods[
                        "difficulty_modifier"
                    ]

                if status_mods["effectiveness"] != 1.0:
                    action_data["effectiveness_modifier"] = status_mods["effectiveness"]

                available_actions.append(action_data)

        # Получаем кризис
        crisis = self._phase2_engine.get_current_crisis()
        crisis_data = None
        if crisis:
            mini_game_data = None
            if crisis.mini_game:
                mini_game_data = {
                    "id": crisis.mini_game.mini_game_id,
                    "name": crisis.mini_game.name,
                    "rules": crisis.mini_game.rules,
                }

            crisis_data = {
                "id": crisis.crisis_id,
                "name": crisis.name,
                "description": crisis.description,
                "important_stats": crisis.important_stats,
                "team_advantages": crisis.team_advantages,
                "mini_game": mini_game_data,
            }

        next_action = self._phase2_engine.get_next_action_to_process()

        # ← НОВОЕ: Детальная история действий
        detailed_history = self._phase2_engine.get_detailed_action_history()

        # ← НОВОЕ: Предварительный расчет для текущего действия
        action_preview = None
        if next_action:
            action_preview = self._phase2_engine.get_action_preview(
                next_action["participants"], next_action["action_type"]
            )

        # Существующий код для объектов, дебафов, фобий, статусов...
        bunker_objects = {}
        for obj_id, obj_state in self.game.phase2_bunker_objects.items():
            bunker_objects[obj_id] = {
                "name": obj_state.name,
                "status": obj_state.status,
                "usable": obj_state.is_usable(),
            }

        team_debuffs = {}
        for team, debuffs in self.game.phase2_team_debuffs.items():
            team_debuffs[team] = [
                {
                    "name": d.name,
                    "stat_penalties": d.stat_penalties,
                    "remaining_rounds": d.remaining_rounds,
                    "source": d.source,
                }
                for d in debuffs
            ]

        active_phobias = {}
        for player_id, phobia in self.game.phase2_player_phobias.items():
            active_phobias[player_id] = {
                "phobia_name": phobia.phobia_name,
                "trigger_source": phobia.trigger_source,
                "affected_stats": phobia.affected_stats,
            }

        active_statuses_full = (
            self._phase2_engine._status_manager.get_statuses_for_api()
        )

        return {
            "phase2": {
                "round": self.game.phase2_round,
                "current_team": self.game.phase2_current_team,
                "bunker_hp": self.game.phase2_bunker_hp,
                "morale": self.game.phase2_morale,
                "supplies": self.game.phase2_supplies,
                "supplies_countdown": self.game.phase2_supplies_countdown,
                "morale_countdown": self.game.phase2_morale_countdown,
                "current_player": current_player,
                "available_actions": available_actions,
                "action_queue": self.game.phase2_action_queue,
                "current_action": next_action,
                "action_preview": action_preview,  # ← НОВОЕ
                "can_process_actions": self._phase2_engine.can_process_actions(),
                "team_turn_complete": self._phase2_engine.is_team_turn_complete(),
                "current_crisis": crisis_data,
                "team_stats": self.game.phase2_team_stats,
                "team_debuffs": team_debuffs,
                "active_phobias": active_phobias,
                "active_statuses": active_statuses_full,
                "bunker_objects": bunker_objects,
                "action_log": self.game.phase2_action_log,  # общая история
                "detailed_history": detailed_history,  # ← НОВОЕ: детальная история
                "winner": self.game.winner,
            }
        }

    def _is_last_player(self) -> bool:
        return self.game.current_idx >= len(self.game.turn_order) - 1

    def _can_execute_action(self, action: GameAction) -> bool:
        """Проверить можно ли выполнить действие"""
        available = self._get_available_actions()
        print(f"Available actions: {available}")
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
            actions = []
            if self._phase2_engine:
                # Добавляем make_action если есть текущий игрок
                if self._phase2_engine.get_current_player():
                    actions.append("make_action")

                # Добавляем process_action если можем обрабатывать
                if self._phase2_engine.can_process_actions():
                    actions.append("process_action")

                # Добавляем resolve_crisis если есть кризис
                if self._phase2_engine.get_current_crisis():
                    actions.append("resolve_crisis")

                # Добавляем finish_team_turn если ход команды завершен и нет действий
                current_team = self._phase2_engine._team_states.get(
                    self.game.phase2_current_team
                )
                if (
                    current_team
                    and current_team.is_complete()
                    and (
                        len(self.game.phase2_action_queue) == 0
                        or self.game.phase2_current_action_index
                        >= len(self.game.phase2_action_queue)
                    )
                ):
                    actions.append("finish_team_turn")
            return actions
        else:
            return []
