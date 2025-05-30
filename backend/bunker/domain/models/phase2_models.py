from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass(slots=True)
class Phase2ActionDef:
    """Определение действия Phase2 из конфига"""

    id: str
    name: str
    team: str  # "outside" | "bunker"
    difficulty: int
    required_stats: List[str]
    stat_weights: Dict[str, float]
    effects: Dict[str, Dict[str, Any]]  # success/failure -> effects

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
            effects=raw.get("effects", {"success": {}, "failure": {}}),
        )


@dataclass(slots=True)
class Phase2CrisisDef:
    """Определение кризиса Phase2 из конфига"""

    id: str
    name: str
    description: str
    important_stats: List[str]
    penalty_on_fail: Dict[str, Any]

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
