from __future__ import annotations
from typing import Dict, List, Set
from bunker.domain.models.models import Game, BunkerObjectState
from bunker.domain.models.character import Character
from bunker.domain.models.bunker_object import BunkerObject


class BunkerObjectBonusCalculator:
    """Калькулятор бонусов от объектов бункера"""

    def __init__(self, game: Game, bunker_objects_data: Dict[str, BunkerObject]):
        self.game = game
        self.bunker_objects_data = bunker_objects_data

    def calculate_team_bonuses(self, team_players: Set[str]) -> Dict[str, int]:
        """Рассчитать бонусы от всех рабочих объектов для команды"""
        total_bonuses = {}

        for obj_id, obj_state in self.game.phase2_bunker_objects.items():
            if not obj_state.is_usable():  # объект поврежден
                continue

            if obj_id not in self.bunker_objects_data:
                continue

            obj_def = self.bunker_objects_data[obj_id]
            obj_bonuses = self._calculate_object_bonus(obj_def, team_players)

            # Суммируем бонусы
            for stat, bonus in obj_bonuses.items():
                total_bonuses[stat] = total_bonuses.get(stat, 0) + bonus

        return total_bonuses

    def _calculate_object_bonus(
        self, obj_def: BunkerObject, team_players: Set[str]
    ) -> Dict[str, int]:
        """Рассчитать бонус от одного объекта"""
        if not obj_def.base_bonus:
            return {}

        # Находим все уникальные черты в команде
        team_traits = self._get_team_traits(team_players)

        # Рассчитываем множитель бонуса
        total_multiplier = 1.0
        applied_bonuses = []

        for trait_type, trait_values in obj_def.trait_bonuses.items():
            for trait_value, multiplier in trait_values.items():
                if trait_type in team_traits and trait_value in team_traits[trait_type]:
                    total_multiplier += multiplier
                    applied_bonuses.append(
                        f"{trait_type}:{trait_value}:+{int(multiplier*100)}%"
                    )

        # Применяем множитель к базовому бонусу
        final_bonuses = {}
        for stat, base_value in obj_def.base_bonus.items():
            final_bonuses[stat] = int(base_value * total_multiplier)

        return final_bonuses

    def _get_team_traits(self, team_players: Set[str]) -> Dict[str, Set[str]]:
        """Получить все уникальные черты команды"""
        team_traits = {}

        for player_id in team_players:
            if player_id not in self.game.characters:
                continue

            character = self.game.characters[player_id]

            for trait_type, trait_obj in character.traits.items():
                if trait_type not in team_traits:
                    team_traits[trait_type] = set()
                team_traits[trait_type].add(trait_obj.name)

        return team_traits

    def get_object_details_for_ui(
        self, obj_id: str, team_players: Set[str]
    ) -> Dict[str, Any]:
        """Получить детальную информацию об объекте для UI"""
        if obj_id not in self.bunker_objects_data:
            return {}

        obj_def = self.bunker_objects_data[obj_id]
        obj_state = self.game.phase2_bunker_objects.get(obj_id)

        if not obj_state:
            return {}

        result = {
            "name": obj_state.name,
            "status": obj_state.status,
            "usable": obj_state.is_usable(),
            "base_bonus": obj_def.base_bonus,
            "current_bonus": {},
            "active_traits": [],
            "available_traits": [],
        }

        if obj_state.is_usable():
            # Рассчитываем текущий бонус
            result["current_bonus"] = self._calculate_object_bonus(
                obj_def, team_players
            )

            # Находим активные черты
            team_traits = self._get_team_traits(team_players)

            for trait_type, trait_values in obj_def.trait_bonuses.items():
                for trait_value, multiplier in trait_values.items():
                    trait_info = {
                        "type": trait_type,
                        "value": trait_value,
                        "bonus": f"+{int(multiplier*100)}%",
                        "active": (
                            trait_type in team_traits
                            and trait_value in team_traits[trait_type]
                        ),
                    }

                    if trait_info["active"]:
                        result["active_traits"].append(trait_info)
                    else:
                        result["available_traits"].append(trait_info)

        return result
