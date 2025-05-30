from __future__ import annotations
from typing import Dict, Iterable

from .character import Character
from .stats import StatRegistry

__all__ = ["calc_team_stats"]


def calc_team_stats(reg: StatRegistry, chars: Iterable[Character]) -> Dict[str, float]:
    base = {s.code: 0.0 for s in reg}
    multipliers = {s.code: 1.0 for s in reg}
    for ch in chars:
        pstats = ch.personal_stats(reg)
        for k in base:
            base[k] += pstats[k]
        tmult = ch.team_multiplier()
        for k, v in tmult.items():
            multipliers[k] *= v
    return {k: round(base[k] * multipliers[k], 1) for k in base}
