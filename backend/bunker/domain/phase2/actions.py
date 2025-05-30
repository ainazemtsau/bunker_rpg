# bunker/domain/phase2/actions.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from ..types import ActionResult, SkillCheck
from ..skills import CharacterStats, TriggerType


class Phase2Action(ABC):
    """Абстрактное действие в Phase2"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def get_skill_check(
        self, character_stats: CharacterStats
    ) -> Optional[SkillCheck]: ...

    @abstractmethod
    def execute(
        self, executor_id: str, target_params: Dict[str, Any], game_state: Any
    ) -> ActionResult: ...


class AttackBunkerAction(Phase2Action):
    """Действие атаки бункера"""

    @property
    def name(self) -> str:
        return "attack"

    @property
    def description(self) -> str:
        return "Атаковать бункер"

    def get_skill_check(self, character_stats: CharacterStats) -> Optional[SkillCheck]:
        return SkillCheck(
            skill_name="attack_bunker",
            base_difficulty=12,
            required_roll=12,
            modifiers={"STRENGTH": 1, "DEXTERITY": 0.5},
        )

    def execute(
        self, executor_id: str, target_params: Dict[str, Any], game_state: Any
    ) -> ActionResult:
        # Логика атаки бункера
        damage = target_params.get("damage", 1)
        return ActionResult(success=True, effects={"damage_dealt": damage})


class RepairBunkerAction(Phase2Action):
    """Действие ремонта бункера"""

    @property
    def name(self) -> str:
        return "repair"

    @property
    def description(self) -> str:
        return "Отремонтировать бункер"

    def get_skill_check(self, character_stats: CharacterStats) -> Optional[SkillCheck]:
        return SkillCheck(
            skill_name="repair_bunker",
            base_difficulty=10,
            required_roll=10,
            modifiers={"INTELLIGENCE": 1, "DEXTERITY": 0.5},
        )

    def execute(
        self, executor_id: str, target_params: Dict[str, Any], game_state: Any
    ) -> ActionResult:
        # Логика ремонта бункера
        heal_amount = target_params.get("heal", 1)
        return ActionResult(success=True, effects={"healing_done": heal_amount})


# bunker/domain/phase2/actions.py
# Добавляем к существующим действиям:


class NoopAction(Phase2Action):
    """Действие ничего не делать"""

    @property
    def name(self) -> str:
        return "noop"

    @property
    def description(self) -> str:
        return "Ничего не делать"

    def get_skill_check(self, character_stats: CharacterStats) -> Optional[SkillCheck]:
        return None  # Никаких проверок не нужно

    def execute(
        self, executor_id: str, target_params: Dict[str, Any], game_state: Any
    ) -> ActionResult:
        return ActionResult(success=True, effects={})


# Обновляем создание реестра в GameEngine:
def _create_default_registry(self) -> ActionRegistry:
    """Создать стандартный реестр действий"""
    registry = ActionRegistry()
    registry.register_action(AttackBunkerAction())
    registry.register_action(RepairBunkerAction())
    registry.register_action(NoopAction())  # Добавляем noop
    return registry


class ActionRegistry:
    """Реестр доступных действий"""

    def __init__(self):
        self._actions: Dict[str, Phase2Action] = {}

    def register_action(self, action: Phase2Action) -> None:
        """Зарегистрировать действие"""
        self._actions[action.name] = action

    def get_action(self, name: str) -> Optional[Phase2Action]:
        """Получить действие по имени"""
        return self._actions.get(name)

    def get_available_actions(self, team: str) -> List[Phase2Action]:
        """Получить доступные действия для команды"""
        if team == "outside":
            return [self._actions.get("attack")]
        else:
            return [self._actions.get("repair")]
