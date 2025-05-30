# bunker/domain/models/enhanced_character.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set
from ..skills import CharacterStats, TraitEffect, TriggerType, StatType, StatModifier


@dataclass
class EnhancedCharacter:
    """Расширенный персонаж с системой навыков"""

    traits: Dict[str, Any] = field(default_factory=dict)
    stats: CharacterStats = field(default_factory=CharacterStats)
    trait_effects: Dict[str, TraitEffect] = field(default_factory=dict)

    def apply_trait_effects(self) -> None:
        """Применить эффекты от всех черт"""
        # Сбрасываем временные модификаторы
        self.stats.temporary_modifiers.clear()
        self.stats.active_effects.clear()

        # Применяем базовые эффекты от черт
        for trait_name, effect in self.trait_effects.items():
            for modifier in effect.base_modifiers:
                self.stats.temporary_modifiers.append(modifier)

            for status in effect.status_effects:
                self.stats.active_effects.add(status)

    def trigger_phobia(self, trigger_type: TriggerType) -> None:
        """Активировать фобию при триггере"""
        for trait_name, effect in self.trait_effects.items():
            if trigger_type in effect.triggers:
                # Применяем штрафы от триггера
                for penalty in effect.trigger_penalties:
                    self.stats.temporary_modifiers.append(penalty)

                # Добавляем статус эффекты
                for status in effect.status_effects:
                    self.stats.active_effects.add(status)

    def has_tag(self, tag: str) -> bool:
        """Проверить наличие тега у персонажа"""
        for effect in self.trait_effects.values():
            if hasattr(effect, "tags") and tag in getattr(effect, "tags", []):
                return True
        return False
