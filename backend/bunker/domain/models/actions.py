from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

__all__ = ("Action",)


@dataclass(slots=True)
class Action:
    id: str
    scope: str  # inside | outside
    name: str
    cost: int = 0
    check: Dict[str, int] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Any) -> "Action":
        if not isinstance(raw, dict) or "id" not in raw:
            raise TypeError("Action must be mapping with an 'id' key")
        return cls(
            id=raw["id"],
            scope=raw.get("scope", "inside"),
            name=raw.get("name", raw["id"]),
            cost=raw.get("cost", 0),
            check=raw.get("check", {}),
            tags=raw.get("tags", []),
        )
