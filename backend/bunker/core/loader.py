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

        # Загружаем обычные коллекции
        for name, factory in LOAD_MAP.items():
            file_path = root / BASE_FILES[name]
            raw = load_any(file_path)
            records = [factory(rec) for rec in raw]
            if name in ("irl_games", "phase2_actions", "phase2_crises"):
                setattr(self, name, {r.id: r for r in records})
            else:
                setattr(self, name, records)

        # Загружаем конфигурацию Phase2 отдельно
        config_path = root / BASE_FILES["phase2_config"]
        config_raw = load_any(config_path)
        self.phase2_config = Phase2Config.from_raw(config_raw)
