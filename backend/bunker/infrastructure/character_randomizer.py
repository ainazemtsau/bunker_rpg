import os
import yaml
import random

CHARACTER_ATTRS = [
    ("profession", "professions.yml"),
    ("hobby", "hobbies.yml"),
    ("health", "healths.yml"),
    ("item", "items.yml"),
    ("phobia", "phobias.yml"),
]

POOLS = {}


def _data_dir():
    # всегда относительный путь к data/ относительно character_randomizer.py
    return os.path.join(os.path.dirname(__file__), "..", "..", "data")


def load_all_character_pools():
    global POOLS
    POOLS = {}
    base_dir = os.path.abspath(_data_dir())
    for attr, fname in CHARACTER_ATTRS:
        full_path = os.path.join(base_dir, fname)
        with open(full_path, encoding="utf-8") as f:
            POOLS[attr] = yaml.safe_load(f)
    return POOLS


def unique_character_sets(player_count: int):
    """Вернёт список случайных уникальных наборов характеристик для игроков"""
    # Для каждого поля берём player_count случайных (без повторов)
    result = []
    pool_copy = {k: random.sample(v, player_count) for k, v in POOLS.items()}
    for i in range(player_count):
        char = {attr: pool_copy[attr][i] for attr, _ in CHARACTER_ATTRS}
        result.append(char)
    random.shuffle(result)  # чтобы не было связи порядок игрока/атрибутов
    return result
