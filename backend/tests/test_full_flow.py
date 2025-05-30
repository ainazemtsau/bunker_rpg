# backend/tests/test_full_flow.py
from pathlib import Path
from collections import Counter
import pytest

from bunker.core.loader import GameData
from bunker.domain.legacy_adapter import GameEngine, Phase, Action
from bunker.domain.models.models import Game, Player

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


@pytest.fixture(scope="module")
def loader() -> GameData:
    return GameData(root=DATA_DIR)


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
    eng.execute(Action.OPEN_BUNKER)
    assert eng.game.bunker_reveal_idx == idx_expected
    assert eng.phase is Phase.REVEAL
    if missing:
        assert missing not in eng.game.turn_order
    assert_current_turn_ok(eng)


def reveal_for_all(eng: GameEngine, attr: str):
    for pid in eng.game.turn_order.copy():
        eng.execute(Action.REVEAL, {"player_id": pid, "attribute": attr})
        if eng.phase is Phase.REVEAL:
            assert_current_turn_ok(eng)


def vote_out_any(eng: GameEngine) -> str:
    target = eng.game.alive_ids()[0]
    for voter in eng.game.alive_ids():
        eng.execute(Action.CAST_VOTE, {"voter_id": voter, "target_id": target})
    eng.execute(Action.REVEAL_RESULTS)
    return target


def test_full_game_and_phase2_flow(loader):
    game = make_game()  # 8 игроков
    eng = GameEngine(game)  # Теперь initializer создается автоматически
    eng.execute(Action.START_GAME)

    # ---------------  ФАЗА 1 ---------------
    open_card(eng, 1)
    reveal_for_all(eng, eng.game.first_round_attribute)
    eng.execute(Action.END_DISCUSSION)

    attrs = ["hobby", "item", "health", "phobia"]
    for idx_card, attr in enumerate(attrs, start=2):
        open_card(eng, idx_card)
        reveal_for_all(eng, attr)
        eng.execute(Action.END_DISCUSSION)
        vote_out_any(eng)

    # Должны перейти в PHASE2
    assert eng.phase is Phase.PHASE2

    # ---------------  ФАЗА 2 ---------------
    # команде outside  — «attack», команде bunker — «noop»
    max_iterations = 100  # Защита от бесконечного цикла
    iteration = 0

    while eng.phase is Phase.PHASE2 and iteration < max_iterations:
        iteration += 1

        # Получаем текущего игрока
        view = eng.view()
        current_player = view["phase2"]["current_player"]

        if current_player is None:
            break

        current_team = view["phase2"]["team"]

        eng.execute(
            Action.MAKE_ACTION,
            {
                "player_id": current_player,
                "action_type": "attack" if current_team == "outside" else "noop",
                "params": {},
            },
        )

    # -------- ПАРТИЯ ЗАКОНЧЕНА -----------
    assert eng.phase is Phase.FINISHED
    assert eng.game.winner in ("outside", "bunker")

    # Лог последнего хода корректен
    last_entry = eng.game.phase2_action_log[-1]
    assert last_entry["team"] in ("outside", "bunker")
    assert "bunker_hp_after" in last_entry
