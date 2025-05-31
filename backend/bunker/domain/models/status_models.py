from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

__all__ = [
    "StatusDef",
    "StatusEffects",
    "ActionModifier",
    "ObjectEffect",
    "PlayerEffect",
    "RemovalCondition",
    "StatusInteractions",
    "StatusUI",
    "ActiveStatus",
]


@dataclass(slots=True)
class ActionModifier:
    """Модификатор действия от статуса"""

    action_id: str
    difficulty_modifier: int = 0
    effectiveness: float = 1.0
    blocked: bool = False

    @classmethod
    def from_raw(cls, raw: Any) -> "ActionModifier":
        if not isinstance(raw, dict) or "action_id" not in raw:
            raise TypeError("ActionModifier must be mapping with 'action_id'")

        return cls(
            action_id=raw["action_id"],
            difficulty_modifier=raw.get("difficulty_modifier", 0),
            effectiveness=raw.get("effectiveness", 1.0),
            blocked=raw.get("blocked", False),
        )


@dataclass(slots=True)
class ObjectEffect:
    """Эффект на объект бункера"""

    object_id: str
    status_change: Optional[str] = None  # working, damaged, destroyed
    effectiveness: float = 1.0

    @classmethod
    def from_raw(cls, raw: Any) -> "ObjectEffect":
        if not isinstance(raw, dict) or "object_id" not in raw:
            raise TypeError("ObjectEffect must be mapping with 'object_id'")

        return cls(
            object_id=raw["object_id"],
            status_change=raw.get("status_change"),
            effectiveness=raw.get("effectiveness", 1.0),
        )


@dataclass(slots=True)
class PlayerEffect:
    """Эффект на игрока"""

    type: str  # stat_penalties, make_useless, phobia_immunity
    stats: Dict[str, int] = field(default_factory=dict)
    target_player: bool = False

    @classmethod
    def from_raw(cls, raw: Any) -> "PlayerEffect":
        if not isinstance(raw, dict) or "type" not in raw:
            raise TypeError("PlayerEffect must be mapping with 'type'")

        return cls(
            type=raw["type"],
            stats=raw.get("stats", {}),
            target_player=raw.get("target_player", False),
        )


@dataclass(slots=True)
class RemovalCondition:
    """Условие снятия статуса"""

    action_id: str

    @classmethod
    def from_raw(cls, raw: Any) -> "RemovalCondition":
        if isinstance(raw, str):
            return cls(action_id=raw)
        if not isinstance(raw, dict) or "action_id" not in raw:
            raise TypeError("RemovalCondition must be str or mapping with 'action_id'")

        return cls(action_id=raw["action_id"])


@dataclass(slots=True)
class StatusInteractions:
    """Взаимодействия между статусами"""

    enhanced_by: List[str] = field(default_factory=list)
    enhances: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Any) -> "StatusInteractions":
        if not isinstance(raw, dict):
            return cls()

        return cls(
            enhanced_by=raw.get("enhanced_by", []),
            enhances=raw.get("enhances", []),
            conflicts_with=raw.get("conflicts_with", []),
            blocks=raw.get("blocks", []),
        )


@dataclass(slots=True)
class StatusUI:
    """UI конфигурация статуса"""

    icon: str
    color: str
    notifications: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Any) -> "StatusUI":
        if not isinstance(raw, dict):
            return cls(icon="warning", color="warning")

        return cls(
            icon=raw.get("icon", "warning"),
            color=raw.get("color", "warning"),
            notifications=raw.get("notifications", {}),
        )


@dataclass(slots=True)
class StatusEffects:
    """Все эффекты статуса"""

    per_round_effects: Dict[str, int] = field(default_factory=dict)
    team_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    action_modifiers: List[ActionModifier] = field(default_factory=list)
    bunker_objects: List[ObjectEffect] = field(default_factory=list)
    triggers_phobias: List[str] = field(default_factory=list)
    player_effects: List[PlayerEffect] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Any) -> "StatusEffects":
        if not isinstance(raw, dict):
            return cls()

        return cls(
            per_round_effects=raw.get("per_round_effects", {}),
            team_stats=raw.get("team_stats", {}),
            action_modifiers=[
                ActionModifier.from_raw(mod) for mod in raw.get("action_modifiers", [])
            ],
            bunker_objects=[
                ObjectEffect.from_raw(obj) for obj in raw.get("bunker_objects", [])
            ],
            triggers_phobias=raw.get("triggers_phobias", []),
            player_effects=[
                PlayerEffect.from_raw(eff) for eff in raw.get("player_effects", [])
            ],
        )


@dataclass(slots=True)
class StatusDef:
    """Определение статуса из конфига"""

    id: str
    name: str
    description: str
    severity: str
    duration_type: str  # rounds, until_removed
    duration_value: int = 0

    effects: StatusEffects = field(default_factory=StatusEffects)
    removal_conditions: List[RemovalCondition] = field(default_factory=list)
    interactions: StatusInteractions = field(default_factory=StatusInteractions)
    ui: StatusUI = field(default_factory=StatusUI)

    @classmethod
    def from_raw(cls, raw: Any) -> "StatusDef":
        if not isinstance(raw, dict) or "id" not in raw:
            raise TypeError("StatusDef must be mapping with 'id'")

        return cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            description=raw.get("description", ""),
            severity=raw.get("severity", "medium"),
            duration_type=raw.get("duration_type", "until_removed"),
            duration_value=raw.get("duration_value", 0),
            effects=StatusEffects.from_raw(raw.get("effects", {})),
            removal_conditions=[
                RemovalCondition.from_raw(cond)
                for cond in raw.get("removal_conditions", [])
            ],
            interactions=StatusInteractions.from_raw(raw.get("interactions", {})),
            ui=StatusUI.from_raw(raw.get("ui", {})),
        )


@dataclass(slots=True)
class ActiveStatus:
    """Активный статус в игре"""

    status_id: str
    applied_at_round: int
    remaining_rounds: int = -1  # -1 для until_removed
    source: str = ""
    enhanced_by: List[str] = field(default_factory=list)

    def is_expired(self, current_round: int) -> bool:
        """Проверить истек ли статус"""
        print(f"Checking expiration for {self.status_id} at round {current_round}")
        if self.remaining_rounds == -1:  # until_removed
            return False

        rounds_passed = current_round - self.applied_at_round
        print(f"Rounds passed: {rounds_passed}, remaining: {self.remaining_rounds}")
        return rounds_passed > self.remaining_rounds

    def to_dict(self) -> Dict[str, Any]:
        """Для сериализации в API"""
        return {
            "status_id": self.status_id,
            "applied_at_round": self.applied_at_round,
            "remaining_rounds": self.remaining_rounds,
            "source": self.source,
            "enhanced_by": self.enhanced_by,
        }
