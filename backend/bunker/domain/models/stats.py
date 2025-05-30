"""Definitions of base stats."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

__all__ = ["StatDef", "StatRegistry"]


@dataclass(frozen=True, slots=True)
class StatDef:
    code: str
    label: str
    desc: str


class StatRegistry:
    """Immutable collection of StatDef objects, indexed by code."""

    def __init__(self, stats: List[StatDef]):
        self._stats: Dict[str, StatDef] = {s.code: s for s in stats}

    def __getitem__(
        self, code: str
    ) -> StatDef:  # noqa: Dunder present for mapping behaviour
        return self._stats[code]

    def __iter__(self):
        return iter(self._stats.values())

    def validate_keys(self, mapping: Dict[str, object], *, ctx: str) -> None:
        unknown = [k for k in mapping if k not in self._stats]
        if unknown:
            raise ValueError(f"{ctx}: unknown stat keys {unknown}")
