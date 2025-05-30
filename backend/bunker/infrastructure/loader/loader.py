from __future__ import annotations

import json
from pathlib import Path
from typing import List
import yaml
from typing import Any
from ...domain.models.models import Character, BunkerCard
from __future__ import annotations
from pathlib import Path
from typing import Dict, List

from ...domain.models.stats import StatDef, StatRegistry
from ...domain.models.traits import Trait
from ...domain.models.phobias import Phobia
from ...domain.models.objects import BunkerObject
from ...domain.models.crises import Crisis
from ...domain.models.irl_games import IRLGame
from ...domain.models.actions import Action


def _load_yaml(path: Path):
    with path.open("r", encoding="utf8") as f:
        if path.suffix == ".json":
            return json.load(f)
        return yaml.safe_load(f)


def import_characters(path: str) -> List[Character]:
    data = _load_yaml(Path(path))
    return [
        Character(
            profession=rec["name"],
            positive=rec["positive"],
            negative=rec["negative"],
            item=rec["item"],
            need=rec["need"],
            skills=rec.get("skills", {}),
        )
        for rec in data
    ]


def import_bunker_cards(path: str) -> List[BunkerCard]:
    data = _load_yaml(Path(path))
    return [BunkerCard(text=str(txt)) for txt in data]


# CLI: python -m bunker.infrastructure.loader.yaml_loader chars.yml bunker.yml
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: loader <characters.yml> <bunker_cards.yml>")
        raise SystemExit(1)

    chars = import_characters(sys.argv[1])
    cards = import_bunker_cards(sys.argv[2])
    print(f"Loaded {len(chars)} characters and {len(cards)} bunker cards")


def load_any(path: str | Path) -> Any:
    path = Path(path)
    with path.open(encoding="utf8") as fh:
        return json.load(fh) if path.suffix == ".json" else yaml.safe_load(fh)


__all__ = ["GameData"]

BASE_FILES = {
    "stats": "stats.yml",
    "professions": "professions.yml",
    "hobbies": "hobbies.yml",
    "healths": "healths.yml",
    "items": "items.yml",
    "personalities": "personalities.yml",
    "secrets": "secrets.yml",
    "phobias": "phobias.yml",
    "bunker_objects": "bunker_objects.yml",
    "crises": "crises.yml",
    "irl_games": "irl_games.yml",
    "actions": "actions.yml",
    "tags": "tags.yml",
}


class GameData:
    """Immutable snapshot of all static data."""

    def __init__(self, *, root: str | Path):
        root = Path(root)
        self.stats = StatRegistry(
            [StatDef(**r) for r in load_any(root / BASE_FILES["stats"])]
        )

        # Trait‑like pools ------------------------------
        def _t(file_key: str) -> List[Trait]:
            raw = load_any(root / BASE_FILES[file_key])
            return [Trait.from_raw(r) for r in raw]

        self.professions = _t("professions")
        self.hobbies = _t("hobbies")
        self.healths = _t("healths")
        self.items = _t("items")
        self.personalities = _t("personalities")
        self.secrets = _t("secrets")

        # Phobias ---------------------------------------
        self.phobias: List[Phobia] = [
            Phobia.from_raw(r) for r in load_any(root / BASE_FILES["phobias"])
        ]

        # Objects / crises / etc. ------------------------
        self.objects = [
            BunkerObject.from_raw(o)
            for o in load_any(root / BASE_FILES["bunker_objects"])
        ]
        self.crises = {
            c.id: c
            for c in (Crisis(**c) for c in load_any(root / BASE_FILES["crises"]))
        }
        self.irl_games = {
            g.id: IRLGame(**g) for g in load_any(root / BASE_FILES["irl_games"])
        }
        self.actions = {
            a.id: Action(**a) for a in load_any(root / BASE_FILES["actions"])
        }
        self.tags: List[str] = load_any(root / BASE_FILES["tags"]) or []

        # Validation ------------------------------------
        self._validate()

    # -------------------- utilities -------------------
    def _validate(self):
        # Ensure all stat keys are legal
        def check(mapping: Dict[str, int], ctx: str):
            self.stats.validate_keys(mapping, ctx=ctx)

        for pool_name in (
            self.professions,
            self.hobbies,
            self.healths,
            self.items,
            self.personalities,
            self.secrets,
        ):
            for t in pool_name:
                for m in (t.add, t.mult, t.team_mult):
                    check(m, f"trait:{t.name}")

        for ph in self.phobias:
            check(ph.add, f"phobia:{ph.name}")
            check(ph.penalty, f"phobia_penalty:{ph.name}")

        for obj in self.objects:
            check(obj.check, f"object:{obj.name}")

        for cr in self.crises.values():
            check(cr.check, f"crisis:{cr.id}")
            check(cr.penalty, f"crisis_penalty:{cr.id}")

        for game in self.irl_games.values():
            self.stats.validate_keys(game.stat_weights, ctx=f"irl_game:{game.id}")

        for act in self.actions.values():
            check(act.check, f"action:{act.id}")

    # ---------------- public helpers ------------------
    def random_character(self, *, rng: random.Random) -> "character.Character":
        from ...domain.models.character import Character  # local import to avoid cycle

        picks = {
            "profession": rng.choice(self.professions),
            "hobby": rng.choice(self.hobbies),
            "health": rng.choice(self.healths),
            "item": rng.choice(self.items),
            "personality": rng.choice(self.personalities),
            "secret": rng.choice(self.secrets),
            "phobia": rng.choice(self.phobias),
        }
        return Character(traits=picks)
