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
from bunker.domain.models.status_models import StatusDef

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
    "phase2_config": Phase2Config.from_raw,
    "statuses": StatusDef.from_raw,
}

BASE_FILES = {k: f"{k}.yml" for k in LOAD_MAP.keys()}


def load_any(path: Path) -> list[Any]:
    import yaml, json

    with path.open(encoding="utf8") as f:
        return yaml.safe_load(f) if path.suffix in {".yml", ".yaml"} else json.load(f)


class GameData:
    def __init__(self, root: Path | str):
        root = Path(root)

        for name, factory in LOAD_MAP.items():
            raw = load_any(root / BASE_FILES[name])

            # ← ИСПРАВЛЕНИЕ для phase2_config (это не список)
            if name == "phase2_config":
                setattr(self, name, factory(raw))
                continue

            records = [factory(rec) for rec in raw]

            # ← ЧЕТКО ОПРЕДЕЛЯЕМ какие коллекции должны быть словарями
            dict_collections = {
                "bunker_objects",
                "phase2_actions",
                "phase2_crises",
                "mini_games",
                "statuses",
            }

            if name in dict_collections:
                # словари по ключу .id
                setattr(self, name, {r.id: r for r in records})
            else:
                # просто список (professions, hobbies, etc)
                setattr(self, name, records)
