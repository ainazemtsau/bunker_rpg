from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

__all__ = ("FailEffect", "Crisis")


@dataclass(slots=True)
class FailEffect:
    """Последствия провала кризиса."""

    penalty: Dict[str, int] = field(default_factory=dict)
    spawn: List[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Any) -> "FailEffect":
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise TypeError("fail_effect must be dict or null")
        return cls(
            penalty=raw.get("penalty", {}),
            spawn=raw.get("spawn", []),
        )


@dataclass(slots=True)
class Crisis:
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    check: Dict[str, int] = field(default_factory=dict)  # командные DC
    fail_effect: FailEffect = field(default_factory=FailEffect)
    irl_game: Optional[str] = None

    # ───────────────────────────── factory ──────────────────────────
    @classmethod
    def from_raw(cls, raw: Any) -> "Crisis":
        if not isinstance(raw, dict) or "id" not in raw:
            raise TypeError("Crisis must be mapping with an 'id' key")

        return cls(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            tags=raw.get("tags", []),
            check=raw.get("check", {}),
            fail_effect=FailEffect.from_raw(raw.get("fail_effect")),
            irl_game=raw.get("irl_game"),
        )
