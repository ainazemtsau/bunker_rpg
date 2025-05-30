from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from enum import Enum


@dataclass(slots=True)
class ActionRequirement:
    """Требование к действию"""

    any_of: List[Dict[str, Any]] = field(default_factory=list)  # ИЛИ
    all_of: List[Dict[str, Any]] = field(default_factory=list)  # И
    not_having: List[Dict[str, Any]] = field(default_factory=list)  # НЕ ИМЕТЬ

    @classmethod
    def from_raw(cls, raw: Any) -> "ActionRequirement":
        if not isinstance(raw, dict):
            return cls()

        return cls(
            any_of=raw.get("any_of", []),
            all_of=raw.get("all_of", []),
            not_having=raw.get("not_having", []),
        )


@dataclass(slots=True)
class Phase2ActionDef:
    """Определение действия Phase2 из конфига"""

    id: str
    name: str
    team: str  # "outside" | "bunker"
    difficulty: int
    required_stats: List[str]
    stat_weights: Dict[str, float]
    stat_bonuses: Dict[
        str, Dict[str, Dict[str, int]]
    ]  # trait_type -> trait_name -> stat_bonus
    requirements: ActionRequirement
    effects: Dict[str, Dict[str, Any]]  # success/failure -> effects
    removes_status: List[str] = field(
        default_factory=list
    )  # какие статусы убирает при успехе

    @classmethod
    def from_raw(cls, raw: Any) -> "Phase2ActionDef":
        if not isinstance(raw, dict) or "id" not in raw:
            raise TypeError("Phase2Action must be mapping with an 'id' key")

        return cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            team=raw.get("team", "bunker"),
            difficulty=raw.get("difficulty", 10),
            required_stats=raw.get("required_stats", []),
            stat_weights=raw.get("stat_weights", {}),
            stat_bonuses=raw.get("stat_bonuses", {}),
            requirements=ActionRequirement.from_raw(raw.get("requirements", {})),
            effects=raw.get("effects", {"success": {}, "failure": {}}),
            removes_status=raw.get("removes_status", []),
        )


@dataclass(slots=True)
class Phase2CrisisDef:
    """Определение кризиса Phase2 из конфига"""

    id: str
    name: str
    description: str
    important_stats: List[str]
    penalty_on_fail: Dict[str, Any]
    adds_status: List[str] = field(default_factory=list)  # какие статусы добавляет
    triggers_phobias: List[str] = field(default_factory=list)  # какие фобии триггерит

    @classmethod
    def from_raw(cls, raw: Any) -> "Phase2CrisisDef":
        if not isinstance(raw, dict) or "id" not in raw:
            raise TypeError("Phase2Crisis must be mapping with an 'id' key")

        return cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            description=raw.get("description", ""),
            important_stats=raw.get("important_stats", []),
            penalty_on_fail=raw.get("penalty_on_fail", {}),
            adds_status=raw.get("adds_status", []),
            triggers_phobias=raw.get("triggers_phobias", []),
        )


@dataclass(slots=True)
class Phase2Config:
    """Конфигурация Phase2"""

    game_settings: Dict[str, Any]
    victory_conditions: Dict[str, Dict[str, Any]]
    mechanics: Dict[str, Any]
    coefficients: Dict[str, float]

    @classmethod
    def from_raw(cls, raw: Any) -> "Phase2Config":
        if not isinstance(raw, dict):
            raise TypeError("Phase2Config must be mapping")

        return cls(
            game_settings=raw.get("game_settings", {}),
            victory_conditions=raw.get("victory_conditions", {}),
            mechanics=raw.get("mechanics", {}),
            coefficients=raw.get("coefficients", {}),
        )
