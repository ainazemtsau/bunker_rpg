from __future__ import annotations
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from bunker.domain.phase2.bunker_objects import BunkerObjectBonusCalculator
from bunker.core.loader import GameData
from bunker.domain.models.models import (
    Game,
    BunkerObjectState,
    DebuffEffect,
    PhobiaStatus,
)
from bunker.domain.models.character import Character
from bunker.domain.models.phase2_models import (
    Phase2ActionDef,
    Phase2CrisisDef,
    Phase2Config,
)
from .types import (
    MiniGameInfo,
    Phase2Action,
    ActionGroup,
    ActionResult,
    CrisisEvent,
    TeamTurnState,
    Phase2ActionType,
    CrisisResult,
)
from .action_filter import ActionFilter
from .status_manager import StatusManager


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
        self._action_filter = ActionFilter(game)

        # Калькулятор бонусов объектов
        self._bunker_bonus_calc = BunkerObjectBonusCalculator(
            game, game_data.bunker_objects
        )
        self._status_manager = StatusManager(game, game_data)

    def initialize_phase2(self) -> None:
        """Инициализация Phase2"""
        # Настройка базовых параметров из конфига
        settings = self.config.game_settings
        self.game.phase2_bunker_hp = settings.get("starting_bunker_hp", 7)
        self.game.phase2_morale = settings.get("starting_morale", 10)
        self.game.phase2_supplies = settings.get("starting_supplies", 8)
        self.game.phase2_round = 1
        self.game.phase2_current_team = "outside"

        # Сбрасываем счетчики поражений
        self.game.phase2_supplies_countdown = 0
        self.game.phase2_morale_countdown = 0

        # Очистка состояний
        self.game.phase2_action_queue.clear()
        self.game.phase2_processed_actions.clear()
        self.game.phase2_current_action_index = 0
        self.game.phase2_action_log.clear()
        self.game.winner = None

        # Инициализация объектов бункера
        self._setup_bunker_objects()

        # Очистка эффектов
        self.game.phase2_team_debuffs.clear()
        self.game.phase2_player_phobias.clear()
        self.game.phase2_active_statuses.clear()

        # Инициализация команд
        self._setup_teams()
        self._calculate_team_stats()
        if not hasattr(self.game, "phase2_active_statuses_detailed"):
            self.game.phase2_active_statuses_detailed = {}

    def _setup_bunker_objects(self) -> None:
        """Настройка начальных объектов бункера"""
        self.game.phase2_bunker_objects.clear()

        initial_objects = self.config.game_settings.get("initial_bunker_objects", [])
        print(f"Setting up bunker objects: {len(initial_objects)} objects found")

        for obj_data in initial_objects:
            obj = BunkerObjectState(
                object_id=obj_data["id"],
                name=obj_data["name"],
                status=obj_data.get("status", "working"),
            )
            self.game.phase2_bunker_objects[obj.object_id] = obj
            print(f"  Added object: {obj.object_id} ({obj.name}) - {obj.status}")

        print(
            f"Total bunker objects initialized: {len(self.game.phase2_bunker_objects)}"
        )

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
        """Расчет характеристик команд с учетом дебафов, фобий, объектов И СТАТУСОВ"""
        stats = {}

        for team_name, team_state in self._team_states.items():
            team_stats = {"ЗДР": 0, "СИЛ": 0, "ИНТ": 0, "ТЕХ": 0, "ЭМП": 0, "ХАР": 0}

            # Базовые статы игроков (существующий код)
            for player_id in team_state.players:
                if player_id in self.game.characters:
                    char_stats = self.game.characters[player_id].aggregate_stats()

                    # Применяем эффекты фобий
                    if player_id in self.game.phase2_player_phobias:
                        phobia = self.game.phase2_player_phobias[player_id]
                        for stat, penalty in phobia.affected_stats.items():
                            if stat in char_stats:
                                char_stats[stat] = max(
                                    char_stats[stat] + penalty,
                                    self.config.mechanics.get("phobia_stat_floor", -2),
                                )

                    # Суммируем в командные статы
                    for stat, value in char_stats.items():
                        if stat in team_stats:
                            team_stats[stat] += value

            # Применяем командные дебафы (существующий код)
            if team_name in self.game.phase2_team_debuffs:
                for debuff in self.game.phase2_team_debuffs[team_name]:
                    for stat, penalty in debuff.stat_penalties.items():
                        if stat in team_stats:
                            team_stats[stat] += penalty

            # Применяем бонусы от объектов бункера (существующий код)
            if team_name == "bunker":
                team_players = set(team_state.players)
                object_bonuses = self._bunker_bonus_calc.calculate_team_bonuses(
                    team_players
                )
                for stat, bonus in object_bonuses.items():
                    if stat in team_stats:
                        team_stats[stat] += bonus

            # ← НОВОЕ: Применяем модификаторы от статусов
            status_modifiers = self._status_manager.get_team_stat_modifiers()
            if team_name in status_modifiers:
                for stat, modifier in status_modifiers[team_name].items():
                    if stat in team_stats:
                        team_stats[stat] += modifier

            stats[team_name] = team_stats

        self.game.phase2_team_stats = stats

    def get_bunker_objects_details(self) -> Dict[str, Any]:
        """Получить детальную информацию о всех объектах бункера для UI"""
        team_players = set(
            self._team_states.get("bunker", TeamTurnState("bunker", [], 0, {})).players
        )

        objects_details = {}
        for obj_id in self.game.phase2_bunker_objects:
            objects_details[obj_id] = self._bunker_bonus_calc.get_object_details_for_ui(
                obj_id, team_players
            )

        return objects_details

    def get_available_actions_for_player(self, player_id: str) -> List[Phase2ActionDef]:
        """Получить доступные действия для конкретного игрока"""
        if player_id in self.game.team_in_bunker:
            team = "bunker"
        elif player_id in self.game.team_outside:
            team = "outside"
        else:
            print(f"Player {player_id} not in any team!")
            return []

        available = self._action_filter.get_available_actions(
            player_id, team, self.data.phase2_actions
        )

        print(
            f"Available actions for {player_id} (team {team}): {[a.id for a in available]}"
        )
        return available

    def get_available_actions(self, team: str) -> List[Phase2ActionDef]:
        """Получить доступные действия для команды (общий список)"""
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
        print(f"\n--- Adding player action for action_id - {action_id}---")
        current_team = self._team_states.get(self.game.phase2_current_team)
        if not current_team or current_team.get_current_player() != player_id:
            return False

        # Проверяем доступность действия для игрока
        available_actions = self.get_available_actions_for_player(player_id)
        print("Available actions for player:", [a.id for a in available_actions])
        action_def = None
        for action in available_actions:
            if action.id == action_id:
                action_def = action
                break
        print(f"Selected action: {action_id} (found: {action_def is not None})")
        if not action_def:
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
            if queued_action["action_type"] == new_action.action_type:
                # Добавляем игрока к существующей группе
                queued_action["participants"].append(new_action.player_id)
                queued_action["params"].update(new_action.params)
                return

        # Создаем новую группу
        self.game.phase2_action_queue.append(
            {
                "action_type": new_action.action_type,
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
        """Обработать текущее действие С НОВОЙ ЛОГИКОЙ"""
        if self.game.phase2_current_action_index >= len(self.game.phase2_action_queue):
            raise ValueError("No actions to process")

        action_data = self.game.phase2_action_queue[
            self.game.phase2_current_action_index
        ]
        action_def = self.data.phase2_actions[action_data["action_type"]]

        # Получаем детальную информацию ДО выполнения
        action_preview = self.get_action_preview(
            action_data["participants"], action_data["action_type"]
        )

        # Проверяем модификаторы от статусов
        status_modifiers = self._status_manager.get_action_modifiers(
            action_data["action_type"]
        )

        if status_modifiers["blocked"]:
            # Действие заблокировано - сохраняем результат и переходим дальше
            result = ActionResult(
                success=False,
                participants=action_data["participants"],
                action_type=Phase2ActionType(action_data["action_type"]),
                roll_result=0,
                combined_stats=0,
                difficulty=action_def.difficulty,
                effects={"blocked_by_statuses": status_modifiers["blocking_statuses"]},
            )
            self._save_action_result(
                action_data, result, action_preview, status_modifiers, blocked=True
            )
            self.game.phase2_current_action_index += 1
            return result

        # Расчет статистик и бросок
        combined_stats = self._calculate_action_stats_with_bonuses(
            action_data["participants"], action_def
        )
        combined_stats = int(combined_stats * status_modifiers["effectiveness"])

        roll = self.rng.randint(1, 20)
        modified_difficulty = (
            action_def.difficulty + status_modifiers["difficulty_modifier"]
        )
        total = roll + combined_stats
        success = total >= modified_difficulty

        print(
            f"Action {action_data['action_type']}: roll={roll}, stats={combined_stats}, difficulty={modified_difficulty}, success={success}"
        )

        # Создание результата
        result = ActionResult(
            success=success,
            participants=action_data["participants"],
            action_type=Phase2ActionType(action_data["action_type"]),
            roll_result=roll,
            combined_stats=combined_stats,
            difficulty=modified_difficulty,
            effects={},
        )

        # ← НОВАЯ ЛОГИКА
        if success:
            # Успех - применяем эффекты успеха и снимаем статусы
            effects = action_def.effects.get("success", {})
            self._apply_action_effects(effects, result, action_def)
            self._check_status_removal(action_data["action_type"])
            print(f"Action succeeded, applied effects: {effects}")

        else:
            # Провал
            if action_def.team == "bunker":
                # Команда бункера - запускаем мини-игру
                mini_game_info = self._select_mini_game_for_action(action_def)
                if mini_game_info:
                    result.crisis_triggered = (
                        f"action_minigame_{action_data['action_type']}"
                    )
                    self._current_crisis = self._create_action_minigame_event(
                        action_def, mini_game_info
                    )
                    print(
                        f"Bunker action failed, starting mini-game: {mini_game_info.name}"
                    )
                else:
                    print(
                        f"No mini-game found for failed bunker action {action_def.id}"
                    )
            else:
                # Команда снаружи - применяем эффекты провала сразу
                effects = action_def.effects.get("failure", {})
                self._apply_action_effects(effects, result, action_def)
                print(f"Outside team action failed, applied effects: {effects}")

        # Сохраняем результат
        self._save_action_result(action_data, result, action_preview, status_modifiers)
        self.game.phase2_current_action_index += 1
        return result

    def _save_action_result(
        self,
        action_data: Dict,
        result: ActionResult,
        action_preview: Dict,
        status_modifiers: Dict,
        blocked: bool = False,
    ) -> None:
        """Сохранить результат действия"""
        saved_result = {
            "action_type": action_data["action_type"],
            "participants": action_data["participants"],
            "success": result.success,
            "effects": result.effects,
            "status_modifiers": status_modifiers,
            "preview": action_preview,
            "timestamp": self.game.phase2_round,
        }

        if blocked:
            saved_result["blocked"] = True
            saved_result["blocking_statuses"] = status_modifiers["blocking_statuses"]
        else:
            saved_result.update(
                {
                    "roll": result.roll_result,
                    "combined_stats": result.combined_stats,
                    "difficulty": result.difficulty,
                    "crisis_triggered": result.crisis_triggered,
                }
            )

        self.game.phase2_processed_actions.append(saved_result)

    def _create_action_minigame_event(
        self, action_def: Phase2ActionDef, mini_game_info: MiniGameInfo
    ) -> CrisisEvent:
        """Создать событие мини-игры для провалившегося действия"""
        return CrisisEvent(
            crisis_id=f"action_minigame_{action_def.id}",
            name=f"Испытание: {action_def.name}",
            description=f"Действие '{action_def.name}' провалилось! Команда бункера должна пройти испытание, чтобы избежать негативных последствий.",
            important_stats=list(action_def.stat_weights.keys()),
            team_advantages={},
            penalty_on_fail={
                "action_id": action_def.id,
                "failure_crises": action_def.failure_crises,
            },
            mini_game=mini_game_info,
        )

    def _select_mini_game_for_action(
        self, action_def: Phase2ActionDef
    ) -> Optional[MiniGameInfo]:
        """Выбрать случайную мини-игру для провалившегося действия"""

        # НОВАЯ ЛОГИКА: выбираем из ВСЕХ доступных мини-игр
        all_mini_games = list(self.data.mini_games.values())

        if not all_mini_games:
            print(f"WARNING: No mini-games available")
            return None

        # Выбираем случайную мини-игру из всех доступных
        selected_game = self.rng.choice(all_mini_games)

        print(
            f"Selected random mini-game '{selected_game.name}' for failed action {action_def.id}"
        )

        return MiniGameInfo(
            mini_game_id=selected_game.id,
            name=selected_game.name,
            rules=selected_game.rules,
        )

    def _select_mini_game_for_crisis(self, crisis_id: str) -> Optional[MiniGameInfo]:
        """Выбрать случайную мини-игру для кризиса"""

        # НОВАЯ ЛОГИКА: тоже случайный выбор из всех
        all_mini_games = list(self.data.mini_games.values())

        if not all_mini_games:
            print(f"WARNING: No mini-games available for crisis {crisis_id}")
            return None

        # Выбираем случайную мини-игру
        selected_game = self.rng.choice(all_mini_games)
        print(
            f"Selected random mini-game '{selected_game.name}' for crisis {crisis_id}"
        )

        return MiniGameInfo(
            mini_game_id=selected_game.id,
            name=selected_game.name,
            rules=selected_game.rules,
        )

    def _create_action_failure_event(
        self,
        action_def: Phase2ActionDef,
        mini_game_info: MiniGameInfo,
        participants: List[str],
    ) -> CrisisEvent:
        """Создать событие для провалившегося действия с мини-игрой"""
        return CrisisEvent(
            crisis_id=f"action_failure_{action_def.id}",
            name=f"Неудача: {action_def.name}",
            description=f"Действие '{action_def.name}' провалилось. Команда должна сыграть в мини-игру чтобы избежать негативных последствий.",
            important_stats=list(action_def.stat_weights.keys()),
            team_advantages={},  # можем рассчитать на основе участников
            penalty_on_fail=action_def.effects.get(
                "failure", {}
            ),  # ← эффекты провала действия
            mini_game=mini_game_info,
        )

    def _check_status_removal(self, action_id: str) -> List[str]:
        """Проверить и снять статусы при успешном действии"""
        removed_statuses = []

        for status_id in list(self.game.phase2_active_statuses):
            if self._status_manager.can_remove_status(status_id, action_id):
                self._status_manager.remove_status(status_id)
                removed_statuses.append(status_id)

        return removed_statuses

    def _calculate_action_stats_with_bonuses(
        self, participants: List[str], action_def: Phase2ActionDef
    ) -> int:
        """Расчет комбинированных характеристик участников с бонусами от черт"""
        total = 0

        for player_id in participants:
            if player_id in self.game.characters:
                char_stats = self.game.characters[player_id].aggregate_stats()

                # Применяем фобии (обнуляем характеристики если активна фобия)
                if player_id in self.game.phase2_player_phobias:
                    phobia = self.game.phase2_player_phobias[player_id]
                    for stat, penalty in phobia.affected_stats.items():
                        if stat in char_stats:
                            char_stats[stat] = max(
                                char_stats[stat] + penalty,
                                self.config.mechanics.get("phobia_stat_floor", -2),
                            )

                # Получаем бонусы от черт для этого действия
                trait_bonuses = self._action_filter.calculate_action_effectiveness(
                    player_id, action_def
                )

                # Применяем бонусы к характеристикам
                for stat, bonus in trait_bonuses.items():
                    if stat in char_stats:
                        char_stats[stat] += bonus

                # Считаем вклад в действие
                for stat, weight in action_def.stat_weights.items():
                    total += char_stats.get(stat, 0) * weight

        # Бонус за групповое действие
        if len(participants) > 1:
            group_bonus = self.config.coefficients.get("group_action_bonus", 0.5)
            total += len(participants) * group_bonus

        return int(total)

    def _apply_action_effects(
        self, effects: Dict[str, Any], result: ActionResult, action_def: Phase2ActionDef
    ) -> None:
        """Применить эффекты действия С ПОДДЕРЖКОЙ СТАТУСОВ"""
        print(f"\n--- Applying action effects ---")
        print(f"Effects to apply: {effects}")

        result.effects = effects.copy()

        # Урон/лечение бункера
        if "bunker_damage" in effects:
            damage = effects["bunker_damage"]
            print(f"Applying bunker damage: {damage}")
            self.game.phase2_bunker_hp -= damage
            self.game.phase2_bunker_hp = max(0, self.game.phase2_bunker_hp)
            print(f"New bunker HP: {self.game.phase2_bunker_hp}")

        if "bunker_heal" in effects:
            heal = effects["bunker_heal"]
            print(f"Applying bunker heal: {heal}")
            # ← ИСПРАВЛЕНИЕ: используем max_bunker_hp если есть, иначе starting_bunker_hp
            max_hp = self.config.game_settings.get(
                "max_bunker_hp", self.config.game_settings.get("starting_bunker_hp", 10)
            )
            old_hp = self.game.phase2_bunker_hp
            self.game.phase2_bunker_hp += heal
            self.game.phase2_bunker_hp = min(max_hp, self.game.phase2_bunker_hp)
            print(
                f"Bunker HP: {old_hp} + {heal} = {old_hp + heal}, capped at {max_hp} = {self.game.phase2_bunker_hp}"
            )

        # Урон/лечение морали
        if "morale_damage" in effects:
            damage = effects["morale_damage"]
            print(f"Applying morale damage: {damage}")
            self.game.phase2_morale -= damage
            self.game.phase2_morale = max(0, self.game.phase2_morale)
            print(f"New morale: {self.game.phase2_morale}")

        if "morale_heal" in effects:
            heal = effects["morale_heal"]
            print(f"Applying morale heal: {heal}")
            max_morale = self.config.game_settings.get(
                "max_morale", self.config.game_settings.get("starting_morale", 10)
            )
            old_morale = self.game.phase2_morale
            self.game.phase2_morale += heal
            self.game.phase2_morale = min(max_morale, self.game.phase2_morale)
            print(
                f"Morale: {old_morale} + {heal} = {old_morale + heal}, capped at {max_morale} = {self.game.phase2_morale}"
            )

        # Урон/лечение припасов
        if "supplies_damage" in effects:
            damage = effects["supplies_damage"]
            print(f"Applying supplies damage: {damage}")
            self.game.phase2_supplies -= damage
            self.game.phase2_supplies = max(0, self.game.phase2_supplies)
            print(f"New supplies: {self.game.phase2_supplies}")

        if "supplies_heal" in effects:
            heal = effects["supplies_heal"]
            print(f"Applying supplies heal: {heal}")
            max_supplies = self.config.game_settings.get(
                "max_supplies", self.config.game_settings.get("starting_supplies", 10)
            )
            old_supplies = self.game.phase2_supplies
            self.game.phase2_supplies += heal
            self.game.phase2_supplies = min(max_supplies, self.game.phase2_supplies)
            print(
                f"Supplies: {old_supplies} + {heal} = {old_supplies + heal}, capped at {max_supplies} = {self.game.phase2_supplies}"
            )

        if "object_damage" in effects:
            for obj_id in effects["object_damage"]:
                if obj_id in self.game.phase2_bunker_objects:
                    self.game.phase2_bunker_objects[obj_id].status = "damaged"

        # Ремонт объектов
        if "repair_object" in effects:
            obj_id = effects["repair_object"]
            if obj_id in self.game.phase2_bunker_objects:
                self.game.phase2_bunker_objects[obj_id].status = "working"

        # Командные дебафы
        if "team_debuff" in effects:
            debuff_data = effects["team_debuff"]
            target_team = debuff_data["target"]

            debuff = DebuffEffect(
                effect_id=debuff_data["effect"],
                name=debuff_data["effect"],
                stat_penalties=debuff_data["stat_penalties"],
                remaining_rounds=debuff_data["duration"],
                source=f"action_{action_def.id}",
            )

            if target_team not in self.game.phase2_team_debuffs:
                self.game.phase2_team_debuffs[target_team] = []
            self.game.phase2_team_debuffs[target_team].append(debuff)

        # Снятие дебафов
        if "remove_team_debuff" in effects:
            debuff_name = effects["remove_team_debuff"]
            for team in self.game.phase2_team_debuffs:
                self.game.phase2_team_debuffs[team] = [
                    d
                    for d in self.game.phase2_team_debuffs[team]
                    if d.effect_id != debuff_name
                ]

        if "apply_status" in effects:
            status_id = effects["apply_status"]
            success = self._status_manager.apply_status(
                status_id, f"action_{action_def.id}"
            )
            result.effects["status_applied"] = status_id if success else None

        # Снятие статусов
        if "remove_status" in effects:
            status_id = effects["remove_status"]
            success = self._status_manager.remove_status(status_id)
            result.effects["status_removed"] = status_id if success else None

        # Лечение фобии
        if "cure_phobia" in effects and effects["cure_phobia"]:
            cured_players = []
            for participant in result.participants:
                if participant in self.game.phase2_player_phobias:
                    del self.game.phase2_player_phobias[participant]
                    cured_players.append(participant)
            result.effects["phobias_cured"] = cured_players

        self._calculate_team_stats()
        print(
            f"After effects - HP: {self.game.phase2_bunker_hp}, Morale: {self.game.phase2_morale}, Supplies: {self.game.phase2_supplies}"
        )

    def _create_crisis_event(self, crisis_id: str) -> CrisisEvent:
        """Создать событие кризиса с мини-игрой"""
        crisis_def = self.data.phase2_crises.get(crisis_id)
        print(f"Creating crisis event for crisis_id: {crisis_id}")

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

        # Выбираем случайную мини-игру для этого кризиса
        mini_game_info = self._select_mini_game_for_crisis(crisis_id)

        return CrisisEvent(
            crisis_id=crisis_id,
            name=crisis_def.name,
            description=crisis_def.description,
            important_stats=crisis_def.important_stats,
            team_advantages=team_advantages,
            penalty_on_fail=crisis_def.penalty_on_fail,
            mini_game=mini_game_info,
        )

    def _select_mini_game_for_crisis(self, crisis_id: str) -> Optional[MiniGameInfo]:
        """Выбрать случайную мини-игру для кризиса"""
        # Находим все мини-игры, подходящие для этого кризиса
        suitable_games = []
        for mini_game in self.data.mini_games.values():
            if crisis_id in mini_game.crisis_events:
                suitable_games.append(mini_game)

        if not suitable_games:
            print(f"WARNING: No mini-games found for crisis {crisis_id}")
            return None

        # Выбираем случайную из подходящих
        selected_game = self.rng.choice(suitable_games)

        return MiniGameInfo(
            mini_game_id=selected_game.id,
            name=selected_game.name,
            rules=selected_game.rules,
        )

    def get_current_crisis(self) -> Optional[CrisisEvent]:
        """Получить текущий кризис"""
        return self._current_crisis

    def resolve_crisis(self, result: CrisisResult) -> None:
        """Разрешить кризис/мини-игру"""
        if not self._current_crisis:
            return

        if self._current_crisis.crisis_id.startswith("action_minigame_"):
            # Это мини-игра от провалившегося действия
            self._resolve_action_minigame(result)
        else:
            # Обычный кризис - существующая логика
            crisis_def = self.data.phase2_crises.get(self._current_crisis.crisis_id)
            if not crisis_def:
                return

            if result == CrisisResult.BUNKER_LOSE:
                self._apply_crisis_penalties(crisis_def.penalty_on_fail)

                for status in crisis_def.adds_status:
                    self._status_manager.apply_status(
                        status, f"crisis_{self._current_crisis.crisis_id}"
                    )

                self._trigger_phobias(
                    crisis_def.triggers_phobias, self._current_crisis.crisis_id
                )

        # Логируем и очищаем
        self.game.phase2_action_log.append(
            {
                "type": (
                    "minigame"
                    if self._current_crisis.crisis_id.startswith("action_minigame_")
                    else "crisis"
                ),
                "crisis_id": self._current_crisis.crisis_id,
                "result": result.value,
                "round": self.game.phase2_round,
            }
        )

        self._current_crisis = None

    def _resolve_regular_crisis(self, result: CrisisResult) -> None:
        """Разрешить обычный кризис (существующая логика)"""
        crisis_def = self.data.phase2_crises.get(self._current_crisis.crisis_id)
        if not crisis_def:
            return

        if result == CrisisResult.BUNKER_LOSE:
            self._apply_crisis_penalties(crisis_def.penalty_on_fail)

            for status in crisis_def.adds_status:
                self._status_manager.apply_status(
                    status, f"crisis_{self._current_crisis.crisis_id}"
                )

            self._trigger_phobias(
                crisis_def.triggers_phobias, self._current_crisis.crisis_id
            )

    def _resolve_action_minigame(self, result: CrisisResult) -> None:
        """Разрешить мини-игру от провалившегося действия"""
        if result == CrisisResult.BUNKER_WIN:
            # Команда выиграла мини-игру - никаких эффектов
            print("Bunker won mini-game - no negative effects")
            return

        # Команда проиграла мини-игру - выбираем случайный кризис и применяем его
        penalty_data = self._current_crisis.penalty_on_fail
        action_id = penalty_data.get("action_id")
        failure_crises = penalty_data.get("failure_crises", [])

        if not failure_crises:
            print(f"No failure crises defined for action {action_id}")
            return

        # Выбираем случайный кризис
        selected_crisis_id = self.rng.choice(failure_crises)
        crisis_def = self.data.phase2_crises.get(selected_crisis_id)

        if not crisis_def:
            print(f"Crisis {selected_crisis_id} not found")
            return

        print(f"Bunker lost mini-game, applying crisis: {selected_crisis_id}")

        # Применяем ВСЕ эффекты кризиса
        self._apply_crisis_penalties(crisis_def.penalty_on_fail)

        # Добавляем статусы от кризиса
        for status in crisis_def.adds_status:
            self._status_manager.apply_status(status, f"crisis_{selected_crisis_id}")

        # Триггерим фобии
        self._trigger_phobias(crisis_def.triggers_phobias, selected_crisis_id)

        # Обновляем статы команд
        self._calculate_team_stats()

    def _apply_action_failure_effects(self, effects: Dict[str, Any]) -> None:
        """Применить эффекты провалившегося действия"""
        # Переиспользуем существующий метод, но убираем создание кризиса
        temp_action_def = type("TempAction", (), {"id": "temp"})()
        temp_result = type("TempResult", (), {"effects": {}})()

        # Применяем все эффекты кроме crisis_trigger (его обрабатываем отдельно)
        filtered_effects = {k: v for k, v in effects.items() if k != "crisis_trigger"}
        self._apply_action_effects(filtered_effects, temp_result, temp_action_def)

        # Если был crisis_trigger, создаем обычный кризис
        if "crisis_trigger" in effects:
            crisis_id = effects["crisis_trigger"]
            print(f"Action failure triggered additional crisis: {crisis_id}")
            # Можем либо сразу создать кризис, либо отложить на следующий ход
            # Для простоты пока создадим сразу (но это может быть слишком сложно)

    def _apply_crisis_penalties(self, penalties: Dict[str, Any]) -> None:
        """Применить штрафы от кризиса"""
        for effect, value in penalties.items():
            if effect == "bunker_damage":
                self.game.phase2_bunker_hp -= value
                self.game.phase2_bunker_hp = max(0, self.game.phase2_bunker_hp)
            elif effect == "morale_damage":
                self.game.phase2_morale -= value
                self.game.phase2_morale = max(0, self.game.phase2_morale)
            elif effect == "supplies_damage":
                self.game.phase2_supplies -= value
                self.game.phase2_supplies = max(0, self.game.phase2_supplies)
            elif effect == "object_damage":
                for obj_id in value:
                    if obj_id in self.game.phase2_bunker_objects:
                        self.game.phase2_bunker_objects[obj_id].status = "damaged"
            elif effect == "team_debuff":
                debuff_data = value
                target_team = debuff_data["target"]

                debuff = DebuffEffect(
                    effect_id=debuff_data["effect"],
                    name=debuff_data["effect"],
                    stat_penalties=debuff_data["stat_penalties"],
                    remaining_rounds=debuff_data["duration"],
                    source="crisis",
                )

                if target_team not in self.game.phase2_team_debuffs:
                    self.game.phase2_team_debuffs[target_team] = []
                self.game.phase2_team_debuffs[target_team].append(debuff)

    def _trigger_phobias(self, phobia_names: List[str], trigger_source: str) -> None:
        """Триггерить фобии у игроков команды бункера"""
        for player_id in self.game.team_in_bunker:
            if player_id not in self.game.characters:
                continue

            character = self.game.characters[player_id]
            if "phobia" not in character.traits:
                continue

            player_phobia = character.traits["phobia"].name
            if player_phobia in phobia_names:
                # Обнуляем характеристики (делаем их минимальными)
                char_stats = character.aggregate_stats()
                affected_stats = {}
                floor = self.config.mechanics.get("phobia_stat_floor", -2)

                for stat, value in char_stats.items():
                    if value > floor:
                        affected_stats[stat] = floor - value  # отрицательное значение

                phobia_status = PhobiaStatus(
                    phobia_name=player_phobia,
                    trigger_source=trigger_source,
                    affected_stats=affected_stats,
                )

                self.game.phase2_player_phobias[player_id] = phobia_status

    def finish_team_turn(self) -> None:
        """Завершить ход команды"""
        current_team = self._team_states.get(self.game.phase2_current_team)
        if not current_team:
            return

        print(f"\n--- Finishing turn for team {self.game.phase2_current_team} ---")

        # Обновляем дебафы (уменьшаем длительность) - ПЕРЕД проверкой победы
        self._update_debuffs()

        # Если переходим к новому раунду - проверяем условия истощения ресурсов
        if self.game.phase2_current_team == "bunker":
            status_effects = self._status_manager.apply_per_round_effects()
            print("End of round - checking resource depletion...")
            if status_effects:
                self.game.phase2_action_log.append(
                    {
                        "type": "status_effects",
                        "round": self.game.phase2_round,
                        "effects": status_effects,
                    }
                )
            expired_statuses = self._status_manager.update_statuses_for_round()
            if expired_statuses:
                self.game.phase2_action_log.append(
                    {
                        "type": "statuses_expired",
                        "round": self.game.phase2_round,
                        "expired": expired_statuses,
                    }
                )
            # Мораль упала до 0 - увеличиваем счетчик
            if self.game.phase2_morale <= 0:
                self.game.phase2_morale_countdown += 1
                print(
                    f"Morale countdown increased to: {self.game.phase2_morale_countdown}"
                )
            else:
                self.game.phase2_morale_countdown = 0

            # Припасы закончились - увеличиваем счетчик
            if self.game.phase2_supplies <= 0:
                self.game.phase2_supplies_countdown += 1
                print(
                    f"Supplies countdown increased to: {self.game.phase2_supplies_countdown}"
                )
            else:
                self.game.phase2_supplies_countdown = 0

        # Логируем ход команды только если были действия
        if self.game.phase2_processed_actions:
            self.game.phase2_action_log.append(
                {
                    "type": "team_turn",
                    "round": self.game.phase2_round,
                    "team": self.game.phase2_current_team,
                    "actions": list(self.game.phase2_processed_actions),
                    "bunker_hp_after": self.game.phase2_bunker_hp,
                    "morale_after": self.game.phase2_morale,
                    "supplies_after": self.game.phase2_supplies,
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
            print(f"New round started: {self.game.phase2_round}")

        # Перемешиваем порядок игроков в новой команде
        next_team = self._team_states.get(self.game.phase2_current_team)
        if next_team:
            import random

            random.shuffle(next_team.players)
            next_team.current_player_index = 0

        # Пересчитываем статы команд после изменений
        self._calculate_team_stats()

        print(f"Turn finished. New team: {self.game.phase2_current_team}")

    def apply_status_from_crisis(self, crisis_id: str) -> None:
        """Применить статус от кризиса"""
        crisis_def = self.data.phase2_crises.get(crisis_id)
        if not crisis_def:
            return

        # Ищем какой статус добавляет этот кризис
        # Это можно настроить в crisis.yml или в отдельном маппинге
        crisis_to_status = {
            "fire_outbreak": "fire",
            "contamination": "contamination",
            "power_failure": "darkness",
            "structural_damage": "structural_weakness",
        }

        status_id = crisis_to_status.get(crisis_id)
        if status_id:
            self._status_manager.apply_status(status_id, f"crisis_{crisis_id}")

    def _update_debuffs(self) -> None:
        """Обновить дебафы (уменьшить длительность, удалить истекшие)"""
        for team in self.game.phase2_team_debuffs:
            # Уменьшаем длительность и удаляем истекшие
            active_debuffs = []
            for debuff in self.game.phase2_team_debuffs[team]:
                debuff.remaining_rounds -= 1
                if debuff.remaining_rounds > 0:
                    active_debuffs.append(debuff)
            self.game.phase2_team_debuffs[team] = active_debuffs

    def check_victory_conditions(self) -> Optional[str]:
        """Проверить условия победы"""
        print(f"\n--- Checking victory conditions ---")
        print(
            f"Round: {self.game.phase2_round}, Max rounds: {self.config.game_settings.get('max_rounds', 10)}"
        )
        print(f"Bunker HP: {self.game.phase2_bunker_hp}")
        print(
            f"Morale: {self.game.phase2_morale} (countdown: {self.game.phase2_morale_countdown})"
        )
        print(
            f"Supplies: {self.game.phase2_supplies} (countdown: {self.game.phase2_supplies_countdown})"
        )

        # Бункер уничтожен
        if self.game.phase2_bunker_hp <= 0:
            self.game.winner = "outside"
            print(f"VICTORY: Bunker destroyed!")
            return "bunker_destroyed"

        # Мораль упала до 0
        if self.game.phase2_morale <= 0:
            self.game.phase2_morale_countdown += 1
            morale_limit = self.config.game_settings.get("morale_countdown_limit", 1)
            print(
                f"Morale is 0, countdown: {self.game.phase2_morale_countdown}/{morale_limit}"
            )
            if self.game.phase2_morale_countdown >= morale_limit:
                self.game.winner = "outside"
                print(f"VICTORY: Morale broken!")
                return "morale_broken"
        else:
            self.game.phase2_morale_countdown = 0

        # Припасы закончились
        if self.game.phase2_supplies <= 0:
            self.game.phase2_supplies_countdown += 1
            supplies_limit = self.config.game_settings.get(
                "supplies_countdown_limit", 2
            )
            print(
                f"Supplies are 0, countdown: {self.game.phase2_supplies_countdown}/{supplies_limit}"
            )
            if self.game.phase2_supplies_countdown >= supplies_limit:
                self.game.winner = "outside"
                print(f"VICTORY: Supplies exhausted!")
                return "supplies_exhausted"
        else:
            self.game.phase2_supplies_countdown = 0

        # Время истекло - победа бункера
        max_rounds = self.config.game_settings.get("max_rounds", 10)
        if self.game.phase2_round > max_rounds:
            self.game.winner = "bunker"
            print(f"VICTORY: Time limit reached!")
            return "time_limit"

        print(f"No victory condition met yet.")
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

    def get_action_preview(
        self, participants: List[str], action_id: str
    ) -> Dict[str, Any]:
        """Получить предварительную информацию о действии ДО его выполнения"""
        if action_id not in self.data.phase2_actions:
            return {}

        action_def = self.data.phase2_actions[action_id]

        # Получаем модификаторы от статусов
        status_modifiers = self._status_manager.get_action_modifiers(action_id)

        # Детальная информация по каждому участнику
        participants_details = []
        total_stats = 0

        for player_id in participants:
            if player_id not in self.game.characters:
                continue

            character = self.game.characters[player_id]
            base_stats = character.aggregate_stats()

            # Применяем эффекты фобий
            phobia_penalties = {}
            if player_id in self.game.phase2_player_phobias:
                phobia = self.game.phase2_player_phobias[player_id]
                phobia_penalties = phobia.affected_stats
                for stat, penalty in phobia_penalties.items():
                    if stat in base_stats:
                        base_stats[stat] = max(
                            base_stats[stat] + penalty,
                            self.config.mechanics.get("phobia_stat_floor", -2),
                        )

            # Получаем бонусы от черт
            trait_bonuses = self._action_filter.calculate_action_effectiveness(
                player_id, action_def
            )

            # Применяем бонусы к характеристикам
            modified_stats = base_stats.copy()
            for stat, bonus in trait_bonuses.items():
                if stat in modified_stats:
                    modified_stats[stat] += bonus

            # Считаем вклад игрока в действие
            player_contribution = 0
            stat_contributions = {}
            for stat, weight in action_def.stat_weights.items():
                contribution = modified_stats.get(stat, 0) * weight
                player_contribution += contribution
                stat_contributions[stat] = {
                    "base": base_stats.get(stat, 0),
                    "trait_bonus": trait_bonuses.get(stat, 0),
                    "phobia_penalty": phobia_penalties.get(stat, 0),
                    "final": modified_stats.get(stat, 0),
                    "weight": weight,
                    "contribution": contribution,
                }

            participants_details.append(
                {
                    "player_id": player_id,
                    "player_name": (
                        self.game.players[player_id].name
                        if player_id in self.game.players
                        else player_id
                    ),
                    "base_stats": base_stats,
                    "trait_bonuses": trait_bonuses,
                    "phobia_penalties": phobia_penalties,
                    "final_stats": modified_stats,
                    "stat_contributions": stat_contributions,
                    "total_contribution": player_contribution,
                }
            )

            total_stats += player_contribution

        # Бонус за групповое действие
        group_bonus = 0
        if len(participants) > 1:
            group_bonus_rate = self.config.coefficients.get("group_action_bonus", 0.5)
            group_bonus = len(participants) * group_bonus_rate
            total_stats += group_bonus

        # Применяем модификаторы эффективности от статусов
        total_stats = int(total_stats * status_modifiers["effectiveness"])

        # Расчет сложности с модификаторами статусов
        base_difficulty = action_def.difficulty
        modified_difficulty = base_difficulty + status_modifiers["difficulty_modifier"]

        # Расчет шанса успеха
        # Нужно выкинуть >= (modified_difficulty - total_stats) на d20
        required_roll = max(1, modified_difficulty - total_stats)
        success_chance = max(0, min(100, (21 - required_roll) * 5))  # в процентах

        return {
            "action_id": action_id,
            "action_name": action_def.name,
            "participants": participants_details,
            "group_bonus": group_bonus,
            "total_stats": total_stats,
            "base_difficulty": base_difficulty,
            "status_modifiers": status_modifiers,
            "modified_difficulty": modified_difficulty,
            "required_roll": required_roll,
            "success_chance": success_chance,
            "blocked": status_modifiers["blocked"],
            "blocking_statuses": status_modifiers.get("blocking_statuses", []),
        }

    def get_detailed_action_history(self) -> List[Dict[str, Any]]:
        """Получить детальную историю всех действий за игру"""
        detailed_history = []

        for log_entry in self.game.phase2_action_log:
            if log_entry.get("type") == "team_turn" and "actions" in log_entry:
                for action_result in log_entry["actions"]:
                    if "action_type" in action_result:
                        # Преобразуем в детальный формат для UI
                        detailed_action = self._format_action_for_history(
                            action_result, log_entry
                        )
                        detailed_history.append(detailed_action)

            elif log_entry.get("type") == "crisis":
                # Добавляем кризисы в историю
                detailed_history.append(
                    {
                        "type": "crisis",
                        "round": log_entry.get("round", "unknown"),
                        "crisis_id": log_entry["crisis_id"],
                        "result": log_entry["result"],
                        "penalty_applied": log_entry.get("penalty_applied", False),
                    }
                )

        return detailed_history

    def _format_action_for_history(
        self, action_result: Dict[str, Any], log_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Форматировать действие для истории"""
        action_id = action_result["action_type"]
        action_def = self.data.phase2_actions.get(action_id)

        return {
            "type": "action",
            "round": log_entry.get("round", "unknown"),
            "team": log_entry.get("team", "unknown"),
            "action_id": action_id,
            "action_name": action_def.name if action_def else action_id,
            "participants": action_result.get("participants", []),
            "success": action_result.get("success", False),
            "roll": action_result.get("roll", 0),
            "combined_stats": action_result.get("combined_stats", 0),
            "difficulty": action_result.get("difficulty", 0),
            "required_roll": max(
                1,
                action_result.get("difficulty", 0)
                - action_result.get("combined_stats", 0),
            ),
            "effects": action_result.get("effects", {}),
            "status_modifiers": action_result.get("status_modifiers", {}),
            "crisis_triggered": action_result.get("crisis_triggered"),
            "blocked": action_result.get("blocked", False),
            "blocking_statuses": action_result.get("blocking_statuses", []),
        }
