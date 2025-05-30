# bunker/domain/events.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from .types import GameEvent, EventHandler


@dataclass
class BaseGameEvent:
    event_type: str
    data: Dict[str, Any]

    def get_type(self) -> str:
        return self.event_type

    def get_data(self) -> Dict[str, Any]:
        return self.data


class EventBus:
    """Шина событий для игры"""

    def __init__(self):
        self._handlers: List[EventHandler] = []

    def register_handler(self, handler: EventHandler) -> None:
        """Зарегистрировать обработчик событий"""
        self._handlers.append(handler)

    def emit(self, event: GameEvent, game_state: Any) -> None:
        """Отправить событие всем подходящим обработчикам"""
        for handler in self._handlers:
            if handler.can_handle(event):
                handler.handle(event, game_state)


class PhobiaEventHandler:
    """Обработчик событий для фобий"""

    def can_handle(self, event: GameEvent) -> bool:
        return event.get_type() in ["crisis_triggered", "action_failed"]

    def handle(self, event: GameEvent, game_state: Any) -> None:
        # Логика обработки фобий при критических ситуациях
        pass


class CrisisEventHandler:
    """Обработчик критических ситуаций"""

    def can_handle(self, event: GameEvent) -> bool:
        return event.get_type() == "critical_failure"

    def handle(self, event: GameEvent, game_state: Any) -> None:
        # Логика запуска мини-игры для критической ситуации
        pass
