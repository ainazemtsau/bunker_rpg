# phobias.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .traits import Trait

__all__ = ("Phobia",)


@dataclass(slots=True)
class Phobia(Trait):
    # новые поля
    triggers: List[str] = field(default_factory=list)
    penalty: Dict[str, int] = field(default_factory=dict)
    status: Optional[str] = None  # "useless" | "hindrance" | "panic"

    # ───────────────────────────── factory ──────────────────────────
    @classmethod
    def from_raw(cls, raw: Any) -> "Phobia":
        """
        Расширяем базовый парсер Trait и сразу возвращаем Phobia,
        чтобы не мутировать объект после создания.
        """
        if isinstance(raw, str):
            return cls(name=raw)

        if not isinstance(raw, dict) or "name" not in raw:
            raise TypeError("Phobia must be str or mapping with a 'name' key")

        return cls(
            name=raw["name"],
            add=raw.get("add", {}),
            mult=raw.get("mult", {}),
            team_mult=raw.get("team_mult", {}),
            tags=raw.get("tags", []),
            triggers=raw.get("triggers", []),
            penalty=raw.get("on_trigger", {}).get("penalty", {}),
            status=raw.get("on_trigger", {}).get("status"),
        )
