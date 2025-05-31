from __future__ import annotations
from typing import Dict, List, Set, Any
from dataclasses import dataclass

from bunker.domain.models.models import Game
from bunker.domain.models.status_models import StatusDef, ActiveStatus
from bunker.core.loader import GameData


class StatusManager:
    """Менеджер активных статусов в игре"""

    def __init__(self, game: Game, game_data: GameData):
        self.game = game
        self.status_definitions = game_data.statuses

    def apply_status(self, status_id: str, source: str = "") -> bool:
        """Применить статус к игре"""
        if status_id not in self.status_definitions:
            print(f"WARNING: Unknown status {status_id}")
            return False

        # Проверяем что статус не активен (не стакается)
        if self.is_status_active(status_id):
            print(f"Status {status_id} already active, ignoring")
            return False

        status_def = self.status_definitions[status_id]

        # Проверяем конфликты
        for conflict_id in status_def.interactions.conflicts_with:
            if self.is_status_active(conflict_id):
                print(f"Status {status_id} conflicts with active {conflict_id}")
                return False

        # Создаем активный статус
        active_status = ActiveStatus(
            status_id=status_id,
            applied_at_round=self.game.phase2_round,
            remaining_rounds=(
                status_def.duration_value
                if status_def.duration_type == "rounds"
                else -1
            ),
            source=source,
        )

        # Проверяем усиления от других статусов
        for enhancer_id in status_def.interactions.enhanced_by:
            if self.is_status_active(enhancer_id):
                active_status.enhanced_by.append(enhancer_id)

        # Добавляем в игру
        if not hasattr(self.game, "phase2_active_statuses_detailed"):
            self.game.phase2_active_statuses_detailed = {}

        self.game.phase2_active_statuses_detailed[status_id] = active_status

        # Обновляем простой список для совместимости
        if status_id not in self.game.phase2_active_statuses:
            self.game.phase2_active_statuses.append(status_id)

        # Применяем немедленные эффекты
        self._apply_immediate_effects(status_def)

        # Триггерим фобии
        self._trigger_phobias(status_def)

        print(f"Applied status {status_id} from {source}")
        return True

    def remove_status(self, status_id: str) -> bool:
        """Снять статус"""
        if not self.is_status_active(status_id):
            return False

        # Удаляем из детального списка
        if hasattr(self.game, "phase2_active_statuses_detailed"):
            self.game.phase2_active_statuses_detailed.pop(status_id, None)

        # Удаляем из простого списка
        if status_id in self.game.phase2_active_statuses:
            self.game.phase2_active_statuses.remove(status_id)

        # Снимаем эффекты (пересчитываем статы команд)
        self._recalculate_team_effects()

        print(f"Removed status {status_id}")
        return True

    def is_status_active(self, status_id: str) -> bool:
        """Проверить активен ли статус"""
        return status_id in self.game.phase2_active_statuses

    def can_remove_status(self, status_id: str, action_id: str) -> bool:
        """Проверить можно ли снять статус действием"""
        if not self.is_status_active(status_id):
            return False

        status_def = self.status_definitions.get(status_id)
        if not status_def:
            return False

        # Проверяем условия снятия
        for condition in status_def.removal_conditions:
            if condition.action_id == action_id:
                return True

        return False

    def update_statuses_for_round(self) -> List[str]:
        """Обновить статусы на новый раунд, вернуть истекшие"""
        if not hasattr(self.game, "phase2_active_statuses_detailed"):
            return []

        expired_statuses = []
        current_round = self.game.phase2_round

        for status_id, active_status in list(
            self.game.phase2_active_statuses_detailed.items()
        ):
            if active_status.is_expired(current_round):
                expired_statuses.append(status_id)
                self.remove_status(status_id)

        return expired_statuses

    def apply_per_round_effects(self) -> Dict[str, Any]:
        """Применить эффекты статусов за раунд"""
        effects_applied = {}

        for status_id in self.game.phase2_active_statuses:
            status_def = self.status_definitions.get(status_id)
            if not status_def:
                continue

            for resource, change in status_def.effects.per_round_effects.items():
                if resource == "bunker_hp":
                    old_value = self.game.phase2_bunker_hp
                    self.game.phase2_bunker_hp = max(
                        0, self.game.phase2_bunker_hp + change
                    )
                    effects_applied[f"{status_id}_bunker_hp"] = {
                        "old": old_value,
                        "new": self.game.phase2_bunker_hp,
                        "change": change,
                    }

                elif resource == "morale":
                    old_value = self.game.phase2_morale
                    self.game.phase2_morale = max(0, self.game.phase2_morale + change)
                    effects_applied[f"{status_id}_morale"] = {
                        "old": old_value,
                        "new": self.game.phase2_morale,
                        "change": change,
                    }

                elif resource == "supplies":
                    old_value = self.game.phase2_supplies
                    self.game.phase2_supplies = max(
                        0, self.game.phase2_supplies + change
                    )
                    effects_applied[f"{status_id}_supplies"] = {
                        "old": old_value,
                        "new": self.game.phase2_supplies,
                        "change": change,
                    }

        return effects_applied

    def get_action_modifiers(self, action_id: str) -> Dict[str, Any]:
        """Получить модификаторы действия от статусов"""
        modifiers = {
            "difficulty_modifier": 0,
            "effectiveness": 1.0,
            "blocked": False,
            "blocking_statuses": [],
        }

        for status_id in self.game.phase2_active_statuses:
            status_def = self.status_definitions.get(status_id)
            if not status_def:
                continue

            for action_mod in status_def.effects.action_modifiers:
                if action_mod.action_id == action_id:
                    modifiers["difficulty_modifier"] += action_mod.difficulty_modifier
                    modifiers["effectiveness"] *= action_mod.effectiveness

                    if action_mod.blocked:
                        modifiers["blocked"] = True
                        modifiers["blocking_statuses"].append(status_id)

        return modifiers

    def get_team_stat_modifiers(self) -> Dict[str, Dict[str, int]]:
        """Получить модификаторы статов команд от статусов"""
        modifiers = {"bunker": {}, "outside": {}}

        for status_id in self.game.phase2_active_statuses:
            status_def = self.status_definitions.get(status_id)
            if not status_def:
                continue

            for team, team_mods in status_def.effects.team_stats.items():
                if team not in modifiers:
                    continue

                for stat, modifier in team_mods.items():
                    modifiers[team][stat] = modifiers[team].get(stat, 0) + modifier

        return modifiers

    def _apply_immediate_effects(self, status_def: StatusDef) -> None:
        """Применить немедленные эффекты статуса"""
        # Эффекты на объекты бункера
        for obj_effect in status_def.effects.bunker_objects:
            if obj_effect.object_id in self.game.phase2_bunker_objects:
                obj = self.game.phase2_bunker_objects[obj_effect.object_id]

                if obj_effect.status_change:
                    obj.status = obj_effect.status_change
                    print(
                        f"Object {obj_effect.object_id} status changed to {obj_effect.status_change}"
                    )

    def _trigger_phobias(self, status_def: StatusDef) -> None:
        """Триггерить фобии от статуса"""
        if not status_def.effects.triggers_phobias:
            return

        for player_id in self.game.team_in_bunker:
            if player_id not in self.game.characters:
                continue

            character = self.game.characters[player_id]
            if "phobia" not in character.traits:
                continue

            player_phobia = character.traits["phobia"].name
            if player_phobia in status_def.effects.triggers_phobias:
                # Проверяем на особый эффект make_useless
                make_useless = any(
                    eff.type == "make_useless"
                    for eff in status_def.effects.player_effects
                )

                if make_useless:
                    # Применяем паническую атаку
                    self.apply_status("panic_attack", f"phobia_{player_phobia}")
                else:
                    # Обычная фобия - снижаем характеристики
                    from bunker.domain.models.models import PhobiaStatus

                    char_stats = character.aggregate_stats()
                    affected_stats = {}
                    floor = -2  # минимальное значение

                    for stat, value in char_stats.items():
                        if value > floor:
                            affected_stats[stat] = floor - value

                    phobia_status = PhobiaStatus(
                        phobia_name=player_phobia,
                        trigger_source=status_def.id,
                        affected_stats=affected_stats,
                    )

                    self.game.phase2_player_phobias[player_id] = phobia_status

    def _recalculate_team_effects(self) -> None:
        """Пересчитать эффекты команд после изменения статусов"""
        # Этот метод будет вызван из Phase2Engine для пересчета статов
        pass

    def get_statuses_for_api(self) -> List[Dict[str, Any]]:
        """Получить статусы для API с полной информацией"""
        result = []

        for status_id in self.game.phase2_active_statuses:
            status_def = self.status_definitions.get(status_id)
            if not status_def:
                continue

            active_status = None
            if hasattr(self.game, "phase2_active_statuses_detailed"):
                active_status = self.game.phase2_active_statuses_detailed.get(status_id)

            status_data = {
                "id": status_id,
                "name": status_def.name,
                "description": status_def.description,
                "severity": status_def.severity,
                "ui": {"icon": status_def.ui.icon, "color": status_def.ui.color},
                "effects": self._format_effects_for_api(status_def),
                "removal_conditions": [
                    {
                        "action_id": cond.action_id,
                        "description": f"Требуется действие: {cond.action_id}",
                    }
                    for cond in status_def.removal_conditions
                ],
            }

            if active_status:
                status_data["applied_at_round"] = active_status.applied_at_round
                status_data["remaining_rounds"] = active_status.remaining_rounds
                status_data["source"] = active_status.source
                status_data["enhanced_by"] = active_status.enhanced_by

            result.append(status_data)

        return result

    def _format_effects_for_api(self, status_def: StatusDef) -> List[str]:
        """Форматировать эффекты для показа в UI"""
        effects = []

        # Per-round эффекты
        for resource, change in status_def.effects.per_round_effects.items():
            if change > 0:
                effects.append(f"+{change} {resource} каждый раунд")
            else:
                effects.append(f"{change} {resource} каждый раунд")

        # Статы команд
        for team, team_mods in status_def.effects.team_stats.items():
            for stat, modifier in team_mods.items():
                if modifier > 0:
                    effects.append(f"+{modifier} {stat} для команды {team}")
                else:
                    effects.append(f"{modifier} {stat} для команды {team}")

        # Заблокированные действия
        blocked_actions = [
            mod.action_id for mod in status_def.effects.action_modifiers if mod.blocked
        ]
        if blocked_actions:
            effects.append(f"Блокирует действия: {', '.join(blocked_actions)}")

        # Затрудненные действия
        harder_actions = [
            f"{mod.action_id} (+{mod.difficulty_modifier})"
            for mod in status_def.effects.action_modifiers
            if mod.difficulty_modifier > 0 and not mod.blocked
        ]
        if harder_actions:
            effects.append(f"Затрудняет: {', '.join(harder_actions)}")

        # Фобии
        if status_def.effects.triggers_phobias:
            effects.append(
                f"Триггерит фобии: {', '.join(status_def.effects.triggers_phobias)}"
            )

        return effects
