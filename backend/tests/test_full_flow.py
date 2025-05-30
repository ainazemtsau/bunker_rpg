# backend/tests/test_full_flow.py
from pathlib import Path
from collections import Counter
import pytest

from bunker.core.loader import GameData
from bunker.domain.engine import GameEngine
from bunker.domain.game_init import GameInitializer
from bunker.domain.types import GamePhase, ActionType, GameAction
from bunker.domain.models.models import Game, Player

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


@pytest.fixture(scope="module")
def loader() -> GameData:
    return GameData(root=DATA_DIR)


@pytest.fixture(scope="module")
def initializer(loader: GameData) -> GameInitializer:
    return GameInitializer(loader)


def make_game(n: int = 8) -> Game:
    host = Player("Host", "H")
    g = Game(host)
    for i in range(n):
        p = Player(f"P{i}", f"S{i}")
        g.players[p.id] = p
    return g


def assert_current_turn_ok(eng: GameEngine):
    snap = eng.view()
    assert snap["phase"] == "reveal"
    cur = snap["current_turn"]
    assert cur["player_id"] in eng.game.turn_order
    assert len(cur["allowed"]) >= 1


def open_card(eng: GameEngine, idx_expected: int, missing: str | None = None):
    action = GameAction(type=ActionType.OPEN_BUNKER)
    eng.execute(action)
    assert eng.game.bunker_reveal_idx == idx_expected
    assert eng._phase is GamePhase.REVEAL
    if missing:
        assert missing not in eng.game.turn_order
    assert_current_turn_ok(eng)


def reveal_for_all(eng: GameEngine, attr: str):
    for pid in eng.game.turn_order.copy():
        action = GameAction(
            type=ActionType.REVEAL, payload={"player_id": pid, "attribute": attr}
        )
        eng.execute(action)
        if eng._phase is GamePhase.REVEAL:
            assert_current_turn_ok(eng)


def vote_out_any(eng: GameEngine) -> str:
    target = eng.game.alive_ids()[0]
    for voter in eng.game.alive_ids():
        action = GameAction(
            type=ActionType.CAST_VOTE, payload={"voter_id": voter, "target_id": target}
        )
        eng.execute(action)

    action = GameAction(type=ActionType.REVEAL_RESULTS)
    eng.execute(action)
    return target


def test_full_game_and_phase2_flow(initializer: GameInitializer):
    game = make_game()  # 8 игроков
    eng = GameEngine(game, initializer)

    # Start the game
    start_action = GameAction(type=ActionType.START_GAME)
    eng.execute(start_action)

    # ---------------  ФАЗА 1 ---------------
    open_card(eng, 1)
    reveal_for_all(eng, eng.game.first_round_attribute)

    end_discussion_action = GameAction(type=ActionType.END_DISCUSSION)
    eng.execute(end_discussion_action)

    attrs = ["hobby", "item", "health", "phobia"]
    for idx_card, attr in enumerate(attrs, start=2):
        open_card(eng, idx_card)
        reveal_for_all(eng, attr)
        eng.execute(end_discussion_action)
        vote_out_any(eng)

    # Должны перейти в PHASE2
    assert eng._phase is GamePhase.PHASE2

    # ---------------  ФАЗА 2 ---------------
    # команде outside  — «attack», команде bunker — «noop»
    max_iterations = 100  # Защита от бесконечного цикла
    iteration = 0

    while eng._phase is GamePhase.PHASE2 and iteration < max_iterations:
        iteration += 1

        # Получаем текущего игрока
        view = eng.view()
        current_player = view["phase2"]["current_player"]

        if current_player is None:
            break

        current_team = view["phase2"]["team"]

        action = GameAction(
            type=ActionType.MAKE_ACTION,
            payload={
                "player_id": current_player,
                "action_type": "attack" if current_team == "outside" else "noop",
                "params": {},
            },
        )
        eng.execute(action)

    # -------- ПАРТИЯ ЗАКОНЧЕНА -----------
    assert eng._phase is GamePhase.FINISHED
    assert eng.game.winner in ("outside", "bunker")

    # Лог последнего хода корректен
    last_entry = eng.game.phase2_action_log[-1]
    assert last_entry["team"] in ("outside", "bunker")
    assert "bunker_hp_after" in last_entry


def test_lobby_to_bunker_phase(initializer: GameInitializer):
    """Test basic game startup"""
    game = make_game(4)
    eng = GameEngine(game, initializer)

    assert eng._phase is GamePhase.LOBBY

    start_action = GameAction(type=ActionType.START_GAME)
    eng.execute(start_action)

    assert eng._phase is GamePhase.BUNKER
    assert game.status == "in_progress"
    assert len(game.characters) == 4


def test_reveal_phase_mechanics(initializer: GameInitializer):
    """Test reveal phase mechanics"""
    game = make_game(3)
    eng = GameEngine(game, initializer)

    # Start game and open first card
    eng.execute(GameAction(type=ActionType.START_GAME))
    eng.execute(GameAction(type=ActionType.OPEN_BUNKER))

    assert eng._phase is GamePhase.REVEAL

    # Test revealing for first player
    current_turn = eng.view()["current_turn"]
    first_player = current_turn["player_id"]
    allowed_attrs = current_turn["allowed"]

    assert first_player in game.turn_order
    assert len(allowed_attrs) >= 1

    # Reveal attribute for first player
    reveal_action = GameAction(
        type=ActionType.REVEAL,
        payload={"player_id": first_player, "attribute": allowed_attrs[0]},
    )
    eng.execute(reveal_action)

    # Should still be in reveal phase but next player
    if len(game.turn_order) > 1:
        assert eng._phase is GamePhase.REVEAL
        assert game.current_idx == 1
    else:
        assert eng._phase is GamePhase.DISCUSSION


def test_voting_phase(initializer: GameInitializer):
    """Test voting mechanics"""
    game = make_game(3)
    eng = GameEngine(game, initializer)

    # Get to voting phase
    eng.execute(GameAction(type=ActionType.START_GAME))
    eng.execute(GameAction(type=ActionType.OPEN_BUNKER))

    # Reveal for all players (first round)
    reveal_for_all(eng, game.first_round_attribute)
    eng.execute(GameAction(type=ActionType.END_DISCUSSION))

    # Open second card and reveal
    eng.execute(GameAction(type=ActionType.OPEN_BUNKER))
    reveal_for_all(eng, "hobby")
    eng.execute(GameAction(type=ActionType.END_DISCUSSION))

    assert eng._phase is GamePhase.VOTING

    # Vote everyone out
    target = game.alive_ids()[0]
    for voter in game.alive_ids():
        vote_action = GameAction(
            type=ActionType.CAST_VOTE, payload={"voter_id": voter, "target_id": target}
        )
        eng.execute(vote_action)

    # Reveal results
    eng.execute(GameAction(type=ActionType.REVEAL_RESULTS))

    assert target in game.eliminated_ids
