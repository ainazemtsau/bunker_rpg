# bunker/domain/skills.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum


class StatType(Enum):
    CHARISMA = "ХАР"
    INTELLIGENCE = "ИНТ"
    STRENGTH = "СИЛ"
    DEXTERITY = "ЛОВ"
    CONSTITUTION = "ТЕЛ"
    WISDOM = "МУД"


class TriggerType(Enum):
    SOCIAL = "social"
    COMBAT = "combat"
    TECHNICAL = "technical"
    SURVIVAL = "survival"


@dataclass
class StatModifier:
    stat_type: StatType
    value: int


@dataclass
class TraitEffect:
    """Эффект от черты персонажа"""

    base_modifiers: List[StatModifier] = field(default_factory=list)
    triggers: Set[TriggerType] = field(default_factory=set)
    trigger_penalties: List[StatModifier] = field(default_factory=list)
    status_effects: List[str] = field(default_factory=list)


@dataclass
class CharacterStats:
    """Характеристики персонажа"""

    base_stats: Dict[StatType, int] = field(
        default_factory=lambda: {
            StatType.CHARISMA: 0,
            StatType.INTELLIGENCE: 0,
            StatType.STRENGTH: 0,
            StatType.DEXTERITY: 0,
            StatType.CONSTITUTION: 0,
            StatType.WISDOM: 0,
        }
    )
    temporary_modifiers: List[StatModifier] = field(default_factory=list)
    active_effects: Set[str] = field(default_factory=set)

    def get_effective_stat(self, stat_type: StatType) -> int:
        """Получить эффективное значение характеристики с учетом модификаторов"""
        base = self.base_stats.get(stat_type, 0)
        modifiers = sum(
            mod.value for mod in self.temporary_modifiers if mod.stat_type == stat_type
        )
        return base + modifiers


class SkillCheckResolver:
    """Разрешение проверок навыков"""

    def __init__(self, rng=None):
        import random

        self._rng = rng or random.Random()

    def resolve_check(
        self,
        character_stats: CharacterStats,
        skill_check: SkillCheck,
        active_triggers: Set[TriggerType] = None,
    ) -> ActionResult:
        """Разрешить проверку навыка"""
        active_triggers = active_triggers or set()

        # Базовый бросок
        roll = self._rng.randint(1, 20)

        # Применяем модификаторы
        total_modifier = 0
        for stat_name, modifier in skill_check.modifiers.items():
            if hasattr(StatType, stat_name.upper()):
                stat_type = StatType(stat_name.upper())
                stat_value = character_stats.get_effective_stat(stat_type)
                total_modifier += stat_value * modifier

        final_result = roll + total_modifier
        success = final_result >= skill_check.required_roll
        critical_failure = roll == 1 and not success

        return ActionResult(
            success=success,
            critical_failure=critical_failure,
            effects={"roll": roll, "modifier": total_modifier, "final": final_result},
        )
