# bunker/domain/phase2/turn_processor.py
from __future__ import annotations
from typing import Any, Dict, Optional
from ..types import ActionResult
from ..events import EventBus, BaseGameEvent
from ..skills import SkillCheckResolver, CharacterStats
from .actions import ActionRegistry


class TurnProcessor:
    """Обработчик ходов в Phase2"""

    def __init__(self, action_registry: ActionRegistry, event_bus: EventBus):
        self._action_registry = action_registry
        self._event_bus = event_bus
        self._skill_resolver = SkillCheckResolver()

    def process_player_action(
        self, player_id: str, action_type: str, params: Dict[str, Any], game_state: Any
    ) -> ActionResult:
        """Обработать действие игрока"""

        # Получаем действие из реестра
        action = self._action_registry.get_action(action_type)
        if not action:
            return ActionResult(success=False, effects={"error": "Unknown action"})

        # Получаем статы персонажа (заглушка пока)
        character_stats = self._get_character_stats(player_id, game_state)

        # Проверяем навык если нужно
        skill_check = action.get_skill_check(character_stats)
        if skill_check:
            check_result = self._skill_resolver.resolve_check(
                character_stats, skill_check
            )
            if not check_result.success:
                # Отправляем событие о неудаче
                failure_event = BaseGameEvent(
                    "action_failed",
                    {
                        "player_id": player_id,
                        "action_type": action_type,
                        "check_result": check_result,
                    },
                )
                self._event_bus.emit(failure_event, game_state)
                return check_result

        # Выполняем действие
        result = action.execute(player_id, params, game_state)

        # Отправляем событие об успехе
        success_event = BaseGameEvent(
            "action_completed",
            {"player_id": player_id, "action_type": action_type, "result": result},
        )
        self._event_bus.emit(success_event, game_state)

        return result

    def _get_character_stats(self, player_id: str, game_state: Any) -> CharacterStats:
        """Получить статы персонажа (заглушка)"""
        # TODO: Реализовать получение статов из персонажа
        return CharacterStats()
