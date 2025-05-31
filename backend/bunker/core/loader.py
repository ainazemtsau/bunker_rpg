from pathlib import Path
from typing import Type, Callable, Any

from bunker.domain.models.traits import Trait
from bunker.domain.models.phobias import Phobia
from bunker.domain.models.irl_games import IRLGame
from bunker.domain.models.bunker_object import BunkerObject
from bunker.domain.models.phase2_models import (
    Phase2ActionDef,
    Phase2CrisisDef,
    Phase2Config,
    MiniGameDef,
)

LOAD_MAP: dict[str, Callable[[Any], Any]] = {
    "professions": Trait.from_raw,
    "hobbies": Trait.from_raw,
    "healths": Trait.from_raw,
    "items": Trait.from_raw,
    "personalities": Trait.from_raw,
    "secrets": Trait.from_raw,
    "phobias": Phobia.from_raw,
    "irl_games": IRLGame.from_raw,
    "bunker_objects": BunkerObject.from_raw,
    "phase2_actions": Phase2ActionDef.from_raw,
    "phase2_crises": Phase2CrisisDef.from_raw,
    "mini_games": MiniGameDef.from_raw,
}

BASE_FILES = {k: f"{k}.yml" for k in LOAD_MAP.keys()}
BASE_FILES["phase2_config"] = "phase2_config.yml"


def load_any(path: Path) -> list[Any]:
    import yaml, json

    with path.open(encoding="utf8") as f:
        return yaml.safe_load(f) if path.suffix in {".yml", ".yaml"} else json.load(f)


class GameData:
    def __init__(self, root: Path | str):
        root = Path(root)

        for name, factory in LOAD_MAP.items():
            raw = load_any(root / BASE_FILES[name])
            records = [factory(rec) for rec in raw]
            # все наши коллекции (professions, crises, bunker_objects и т.д.)—
            # это списки, кроме тех, что мы хотим по id.
            if name in ("crises", "irl_games", "actions"):
                # словари по ключу .id
                setattr(self, name, {r.id: r for r in records})
            else:
                # просто список
                setattr(self, name, records)
