from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

__all__ = ("IRLGame",)


@dataclass(slots=True)
class IRLGame:
    id: str
    name: str
    type: str  # physical | mental | party
    rules: str
    stat_weights: Dict[str, float] = field(default_factory=dict)

    # ────────────── factory ──────────────
    @classmethod
    def from_raw(cls, raw: Any) -> "IRLGame":
        if not isinstance(raw, dict) or "id" not in raw:
            raise TypeError("IRL-game must be mapping with an 'id' key")

        return cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            type=raw.get("type", "party"),
            rules=raw.get("rules", ""),
            stat_weights=raw.get("stat_weights", {}),
        )
