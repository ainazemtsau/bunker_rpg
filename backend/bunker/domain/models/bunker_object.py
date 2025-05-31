from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any

__all__ = ("BunkerObject",)


@dataclass(slots=True)
class BunkerObject:
    id: str  # ← ДОБАВЛЕНО поле id
    name: str
    check: Dict[str, int] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    requirements: List[dict] = field(default_factory=list)
    base_bonus: Dict[str, int] = field(default_factory=dict)
    trait_bonuses: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )  # ← ОБНОВЛЕНО

    @classmethod
    def from_raw(cls, raw: Any) -> "BunkerObject":
        if isinstance(raw, str):
            return cls(id=raw, name=raw)
        if not isinstance(raw, dict) or "id" not in raw:
            raise TypeError("Bunker-object must be str or mapping with an 'id' key")
        return cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            check=raw.get("check", {}),
            tags=raw.get("tags", []),
            requirements=raw.get("requirements", []),
            base_bonus=raw.get("base_bonus", {}),
            trait_bonuses=raw.get("trait_bonuses", {}),
        )
