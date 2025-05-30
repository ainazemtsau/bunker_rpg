from pathlib import Path
import bunker.core.loader as cl

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


def test_game_data_load():
    gd = cl.GameData(root=DATA_DIR)
    # Полный список сущностей загружен
    assert gd.professions and gd.phobias and gd.irl_games
    assert gd.phase2_actions and gd.phase2_crises and gd.phase2_config


def test_random_character_and_team_stats():
    gd = cl.GameData(root=DATA_DIR)
    chars = gd.professions[:8]
    assert len(chars) == 8
