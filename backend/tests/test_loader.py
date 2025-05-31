from pathlib import Path
import bunker.core.loader as cl

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


def test_game_data_load():
    gd = cl.GameData(root=DATA_DIR)
    # Полный список сущностей загружен (добавили mini_games)
    assert gd.professions and gd.phobias and gd.irl_games
    assert gd.phase2_actions and gd.phase2_crises and gd.phase2_config
    assert gd.mini_games  # новая проверка


def test_mini_games_structure():
    """Тест структуры мини-игр"""
    gd = cl.GameData(root=DATA_DIR)

    assert len(gd.mini_games) > 0, "Should load mini-games"

    # Проверяем структуру первой мини-игры
    first_game = next(iter(gd.mini_games.values()))
    assert hasattr(first_game, "id"), "Mini-game should have ID"
    assert hasattr(first_game, "name"), "Mini-game should have name"
    assert hasattr(first_game, "rules"), "Mini-game should have rules"
    assert hasattr(first_game, "crisis_events"), "Mini-game should have crisis_events"

    assert isinstance(first_game.crisis_events, list), "crisis_events should be list"
    assert (
        len(first_game.crisis_events) > 0
    ), "Mini-game should have at least one crisis event"


def test_random_character_and_team_stats():
    gd = cl.GameData(root=DATA_DIR)
    chars = gd.professions[:8]  # условно берём 8 профессий как заглушку
    assert len(chars) == 8
