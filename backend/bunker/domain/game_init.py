from __future__ import annotations
import random
from typing import TYPE_CHECKING, List

from bunker.core.loader import GameData
from bunker.domain.models.traits import Trait
from bunker.domain.models.character import Character

if TYPE_CHECKING:
    from bunker.domain.models.models import Game

# Все 7 черт
TRAIT_ATTRS = (
    "profession",
    "hobby",
    "health",
    "item",
    "phobia",
    "personality",
    "secret",
)

PLURAL_MAP = {
    "profession": "professions",
    "hobby": "hobbies",
    "health": "healths",
    "item": "items",
    "phobia": "phobias",
    "personality": "personalities",
    "secret": "secrets",
}


class GameInitializer:
    def __init__(self, data: GameData, rng: random.Random | None = None):
        self._data = data
        self._rng = rng or random.Random()

    def setup_new_game(self, game: Game) -> None:
        self._assign_characters(game)
        self._assign_bunker_cards(game)

    def _assign_characters(self, game: Game) -> None:
        n = len(game.players)
        pools = {}

        for attr in TRAIT_ATTRS:
            collection = getattr(self._data, PLURAL_MAP[attr])
            # ← ИСПРАВЛЕНИЕ: проверяем тип коллекции
            if isinstance(collection, dict):
                pools[attr] = list(collection.values())
            else:
                pools[attr] = list(collection)

        for attr, pool in pools.items():
            if len(pool) < n:
                raise ValueError(
                    f"Pool '{attr}' has only {len(pool)} entries, need {n}"
                )

        sampled = {attr: self._rng.sample(pool, k=n) for attr, pool in pools.items()}

        templates: List[dict[str, Trait]] = []
        for i in range(n):
            tpl = {attr: sampled[attr][i] for attr in TRAIT_ATTRS}
            templates.append(tpl)

        # ← ИСПРАВЛЕНИЕ: код должен быть ВНУТРИ метода с правильным отступом
        self._rng.shuffle(templates)
        for pid, tpl in zip(game.players, templates):
            game.characters[pid] = Character(traits=tpl)

    def _assign_bunker_cards(self, game: Game) -> None:
        # ← ИСПРАВЛЕНИЕ: берем значения из словаря
        cards = list(self._data.bunker_objects.values())
        if len(cards) < 5:
            raise ValueError("Need at least 5 bunker objects")
        game.bunker_cards = self._rng.sample(cards, k=5)
        game.bunker_reveal_idx = 0
