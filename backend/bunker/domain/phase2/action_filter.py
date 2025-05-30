from __future__ import annotations
from typing import List, Dict, Any
from bunker.domain.models.character import Character
from bunker.domain.models.models import Game, BunkerObjectState
from bunker.domain.models.phase2_models import Phase2ActionDef, ActionRequirement


class ActionFilter:
    """Фильтрация доступных действий для игрока"""

    def __init__(self, game: Game):
        self.game = game

    def get_available_actions(
        self, player_id: str, team: str, all_actions: Dict[str, Phase2ActionDef]
    ) -> List[Phase2ActionDef]:
        """Получить список доступных действий для игрока"""
        if player_id not in self.game.characters:
            return []

        character = self.game.characters[player_id]
        available = []

        for action in all_actions.values():
            if action.team != team:
                continue

            if self._can_player_perform_action(player_id, character, action):
                available.append(action)

        return available

    def _can_player_perform_action(
        self, player_id: str, character: Character, action: Phase2ActionDef
    ) -> bool:
        """Проверить может ли игрок выполнить действие"""
        req = action.requirements

        # Проверяем обязательные требования (all_of)
        if req.all_of and not self._check_all_of(player_id, character, req.all_of):
            return False

        # Проверяем альтернативные требования (any_of)
        if req.any_of and not self._check_any_of(player_id, character, req.any_of):
            return False

        # Проверяем запрещающие требования (not_having)
        if req.not_having and self._check_any_of(player_id, character, req.not_having):
            return False

        return True

    def _check_all_of(
        self, player_id: str, character: Character, requirements: List[Dict[str, Any]]
    ) -> bool:
        """Проверить что ВСЕ требования выполнены"""
        for req in requirements:
            if not self._check_single_requirement(player_id, character, req):
                return False
        return True

    def _check_any_of(
        self, player_id: str, character: Character, requirements: List[Dict[str, Any]]
    ) -> bool:
        """Проверить что хотя бы ОДНО требование выполнено"""
        if not requirements:
            return True

        for req in requirements:
            if self._check_single_requirement(player_id, character, req):
                return True
        return False

    def _check_single_requirement(
        self, player_id: str, character: Character, req: Dict[str, Any]
    ) -> bool:
        """Проверить одно требование"""
        for req_type, req_value in req.items():
            if req_type == "profession":
                if not self._check_trait_requirement(
                    character, "profession", req_value
                ):
                    return False
            elif req_type == "item":
                if not self._check_trait_requirement(character, "item", req_value):
                    return False
            elif req_type == "hobby":
                if not self._check_trait_requirement(character, "hobby", req_value):
                    return False
            elif req_type == "personality":
                if not self._check_trait_requirement(
                    character, "personality", req_value
                ):
                    return False
            elif req_type == "phobia":
                if not self._check_trait_requirement(character, "phobia", req_value):
                    return False
            elif req_type == "bunker_object":
                if not self._check_bunker_object_requirement(req_value, "working"):
                    return False
            elif req_type == "bunker_object_state":
                # Это проверяется вместе с bunker_object
                continue
            elif req_type == "active_status":
                if not self._check_active_status_requirement(req_value):
                    return False
            elif req_type == "active_phobia":
                if req_value and player_id not in self.game.phase2_player_phobias:
                    return False
                elif not req_value and player_id in self.game.phase2_player_phobias:
                    return False
            elif req_type == "target_has_phobia":
                # Для действий лечения фобий - должен быть хотя бы один игрок с фобией в команде
                if req_value and not self._has_team_member_with_phobia(player_id):
                    return False

        return True

    def _check_trait_requirement(
        self, character: Character, trait_type: str, required_values: List[str]
    ) -> bool:
        """Проверить требование к черте персонажа"""
        if trait_type not in character.traits:
            return False

        trait_name = character.traits[trait_type].name
        return trait_name in required_values

    def _check_bunker_object_requirement(
        self, object_id: str, required_state: str = "working"
    ) -> bool:
        """Проверить требование к объекту бункера"""
        if object_id not in self.game.phase2_bunker_objects:
            return False

        obj = self.game.phase2_bunker_objects[object_id]
        return obj.status == required_state

    def _check_active_status_requirement(self, status: str) -> bool:
        """Проверить требование к активному статусу"""
        return status in self.game.phase2_active_statuses

    def _has_team_member_with_phobia(self, player_id: str) -> bool:
        """Проверить есть ли в команде игрок с фобией"""
        if player_id in self.game.team_in_bunker:
            team_members = self.game.team_in_bunker
        else:
            team_members = self.game.team_outside

        for member_id in team_members:
            if member_id in self.game.phase2_player_phobias:
                return True
        return False

    def calculate_action_effectiveness(
        self, player_id: str, action: Phase2ActionDef
    ) -> Dict[str, int]:
        """Рассчитать эффективность действия для игрока (бонусы от черт)"""
        if player_id not in self.game.characters:
            return {}

        character = self.game.characters[player_id]
        bonuses = {}

        # Проходим по всем типам бонусов
        for trait_type, trait_bonuses in action.stat_bonuses.items():
            if trait_type not in character.traits:
                continue

            trait_name = character.traits[trait_type].name
            if trait_name in trait_bonuses:
                trait_bonus = trait_bonuses[trait_name]
                for stat, bonus in trait_bonus.items():
                    bonuses[stat] = bonuses.get(stat, 0) + bonus

        return bonuses
