import yaml
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_characters():
    with open(DATA_DIR / "characters.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_bunker():
    with open(DATA_DIR / "bunker.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_crises():
    with open(DATA_DIR / "crisis.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)
