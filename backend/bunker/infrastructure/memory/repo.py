"""In-memory репозиторий. Для продакшена появится SQLGameRepo."""

from __future__ import annotations
from typing import Dict, Tuple, Optional

from ...domain.models.models import Game, Player


class InMemoryGameRepo:
    def __init__(self):
        self._games: Dict[str, Game] = {}

    # ── game CRUD ───────────────────────────────────────────────
    def save(self, game: Game):
        self._games[game.id] = game

    def get(self, gid: str) -> Optional[Game]:
        return self._games.get(gid)

    def remove(self, gid: str):
        self._games.pop(gid, None)

    # ── helpers ────────────────────────────────────────────────
    def by_sid(self, sid: str) -> Tuple[Game, Player] | None:
        for g in self._games.values():
            if p := g.by_sid(sid):
                return g, p
        return None


# singleton — используем во всём сервис-слое
repo = InMemoryGameRepo()
