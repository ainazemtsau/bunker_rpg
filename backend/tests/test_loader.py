from pathlib import Path
import bunker.core.loader as cl

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")  # ваш абсолютный путь


def test_game_data_load():
    gd = cl.GameData(root=DATA_DIR)
    # Полный список сущностей загружен
    assert gd.professions and gd.phobias and gd.crises and gd.irl_games and gd.actions


def test_random_character_and_team_stats():
    gd = cl.GameData(root=DATA_DIR)
    chars = gd.professions[:8]  # условно берём 8 профессий как заглушку
    assert len(chars) == 8
