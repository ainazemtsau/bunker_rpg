from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List

from bunker.domain.models.traits import Trait

__all__ = ("Character",)


@dataclass(slots=True)
class Character:
    traits: Dict[str, Trait]
    revealed: List[str] = field(default_factory=list)

    def reveal(self, attr: str) -> None:
        if attr in self.traits and attr not in self.revealed:
            self.revealed.append(attr)

    def is_revealed(self, attr: str) -> bool:
        return attr in self.revealed

    def to_public_dict(self) -> Dict[str, str | None]:
        return {
            attr: (
                self.traits[attr].to_dict()
                if attr in self.revealed
                else self.traits[attr].to_dict()
            )
            for attr in self.reveal_order
        }

    def to_owner_dict(self) -> Dict[str, Dict[str, any]]:
        """
        Формирует словарь для фронта, где у каждого трейта есть поле revealed (True/False).
        """
        owner_view = {}
        for attr_key in self.reveal_order:
            if attr_key in self.traits:
                trait_obj = self.traits[attr_key]
                trait_dict = trait_obj.to_dict()
                trait_dict["revealed"] = self.is_revealed(attr_key)
                owner_view[attr_key] = trait_dict
        return owner_view

    @property
    def reveal_order(self) -> List[str]:
        return list(self.traits.keys())

    def aggregate_stats(self) -> Dict[str, int]:
        stats = {}
        for tr in self.traits.values():
            for k, v in getattr(tr, "add", {}).items():
                stats[k] = stats.get(k, 0) + v
        return stats

    def has_tag(self, tag: str) -> bool:
        for tr in self.traits.values():
            if tag in getattr(tr, "tags", []):
                return True
        return False
