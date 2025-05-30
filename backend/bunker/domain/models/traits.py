from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List

__all__ = ("Trait",)


@dataclass(slots=True)
class Trait:
    name: str
    add: Dict[str, int] = field(default_factory=dict)
    mult: Dict[str, float] = field(default_factory=dict)
    team_mult: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Any) -> "Trait":
        if isinstance(raw, str):
            return cls(name=raw)
        if not isinstance(raw, dict) or "name" not in raw:
            raise TypeError("Trait must be str or mapping with a 'name' key")
        return cls(
            name=raw["name"],
            add=raw.get("add", {}),
            mult=raw.get("mult", {}),
            team_mult=raw.get("team_mult", {}),
            tags=raw.get("tags", []),
        )
