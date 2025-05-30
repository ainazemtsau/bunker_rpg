from pathlib import Path
import pytest

from bunker.core.loader import GameData
from bunker.domain.game_init import GameInitializer, TRAIT_ATTRS
from bunker.domain.models.models import Game, Player, Character

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


def make_game_with_players(n: int) -> Game:
    host = Player(name="Host", sid="H")
    g = Game(host=host)
    for i in range(n):
        p = Player(name=f"P{i}", sid=f"S{i}")
        g.players[p.id] = p
    return g


@pytest.fixture(scope="module")
def loader() -> GameData:
    return GameData(root=DATA_DIR)


def test_character_uniqueness_and_count(loader: GameData):
    game = make_game_with_players(8)
    GameInitializer(loader).setup_new_game(game)

    # Должны создаться 8 персонажей
    assert len(game.characters) == 8
    # И все объекты — именно Character
    assert all(isinstance(c, Character) for c in game.characters.values())

    # Проверяем уникальность по каждому признаку
    for attr in TRAIT_ATTRS:
        names = [c.traits[attr].name for c in game.characters.values()]
        assert len(names) == 8, f"wrong count for {attr}"
        assert len(set(names)) == 8, f"duplicates in {attr}"


def test_bunker_cards(loader: GameData):
    game = make_game_with_players(8)
    GameInitializer(loader).setup_new_game(game)

    # 5 скрытых карт
    assert len(game.bunker_cards) == 5
    assert game.bunker_reveal_idx == 0
