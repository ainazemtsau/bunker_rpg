from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any

__all__ = ("BunkerObject",)


@dataclass(slots=True)
class BunkerObject:
    name: str
    check: Dict[str, int] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    requirements: List[dict] = field(default_factory=list)
    base_bonus: Dict[str, int] = field(default_factory=dict)  # новое поле
    trait_bonuses: Dict[str, Dict[str, float]] = field(
        default_factory=dict
    )  # новое поле

    @classmethod
    def from_raw(cls, raw: Any) -> "BunkerObject":
        if isinstance(raw, str):
            return cls(name=raw)
        if not isinstance(raw, dict) or "name" not in raw:
            raise TypeError("Bunker-object must be str or mapping with a 'name'")
        return cls(
            name=raw["name"],
            check=raw.get("check", {}),
            tags=raw.get("tags", []),
            requirements=raw.get("requirements", []),
            base_bonus=raw.get("base_bonus", {}),
            trait_bonuses=raw.get("trait_bonuses", {}),
        )
