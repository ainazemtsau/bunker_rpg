import pytest
from pathlib import Path
from bunker.core.loader import GameData

# Используем основную папку данных
DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


def test_statuses_loading():
    """Тест загрузки статусов из YAML"""
    game_data = GameData(root=DATA_DIR)

    # Проверяем что статусы загрузились
    assert hasattr(game_data, "statuses")
    assert len(game_data.statuses) > 0

    # Проверяем что это словарь по ID
    assert isinstance(game_data.statuses, dict)

    # Проверяем основные статусы
    assert "fire" in game_data.statuses
    assert "darkness" in game_data.statuses
    assert "panic_attack" in game_data.statuses
    assert "high_morale" in game_data.statuses


def test_status_structure():
    """Тест структуры загруженных статусов"""
    game_data = GameData(root=DATA_DIR)

    fire_status = game_data.statuses["fire"]

    # Проверяем основные поля
    assert fire_status.id == "fire"
    assert fire_status.name == "Пожар"
    assert fire_status.severity == "high"
    assert fire_status.duration_type == "until_removed"

    # Проверяем эффекты
    assert fire_status.effects.per_round_effects["bunker_hp"] == -1
    assert fire_status.effects.per_round_effects["morale"] == -1

    # Проверяем модификаторы действий
    repair_modifier = next(
        mod
        for mod in fire_status.effects.action_modifiers
        if mod.action_id == "repair_bunker"
    )
    assert repair_modifier.difficulty_modifier == 3

    blocked_modifier = next(
        mod
        for mod in fire_status.effects.action_modifiers
        if mod.action_id == "search_supplies"
    )
    assert blocked_modifier.blocked is True

    # Проверяем триггеры фобий
    assert "Пирофобия" in fire_status.effects.triggers_phobias

    # Проверяем условия снятия
    assert len(fire_status.removal_conditions) == 1
    assert fire_status.removal_conditions[0].action_id == "extinguish_fire"

    # Проверяем UI
    assert fire_status.ui.icon == "fire"
    assert fire_status.ui.color == "error"
