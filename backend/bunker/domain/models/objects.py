from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any

__all__ = ["BunkerObject"]


@dataclass(slots=True)
class BunkerObject:
    name: str
    check: Dict[str, int] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Any) -> "BunkerObject":
        if isinstance(raw, str):
            return cls(name=raw)
        return cls(
            name=raw["name"], check=raw.get("check", {}), tags=raw.get("tags", [])
        )
