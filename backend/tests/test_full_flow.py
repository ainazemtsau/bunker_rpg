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
def game_data() -> GameData:
    return GameData(root=DATA_DIR)


@pytest.fixture(scope="module")
def initializer(game_data: GameData) -> GameInitializer:
    return GameInitializer(game_data)


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


def open_card(eng: GameEngine, idx_expected: int):
    action = GameAction(type=ActionType.OPEN_BUNKER)
    eng.execute(action)
    assert eng.game.bunker_reveal_idx == idx_expected
    assert eng._phase is GamePhase.REVEAL
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


def test_full_game_and_phase2_flow(game_data: GameData, initializer: GameInitializer):
    """Полный тест игрового флоу включая Phase2"""
    game = make_game(8)  # 8 игроков
    eng = GameEngine(game, initializer, game_data)

    # ===============  ФАЗА 1 ===============
    print("Starting Phase 1...")

    # Начинаем игру
    start_action = GameAction(type=ActionType.START_GAME)
    eng.execute(start_action)
    assert eng._phase is GamePhase.BUNKER
    assert len(game.characters) == 8
    print(f"Characters created: {len(game.characters)}")
    for pid, char in game.characters.items():
        stats = char.aggregate_stats()
        print(f"Player {pid}: {stats}")

    # Первая карта и раскрытие профессий
    open_card(eng, 1)
    reveal_for_all(eng, eng.game.first_round_attribute)

    end_discussion_action = GameAction(type=ActionType.END_DISCUSSION)
    eng.execute(end_discussion_action)
    assert eng._phase is GamePhase.BUNKER

    # Проходим несколько раундов голосования
    attrs = ["hobby", "item", "health", "phobia"]
    for idx_card, attr in enumerate(attrs, start=2):
        print(f"Round with {attr}, alive players: {len(game.alive_ids())}")

        open_card(eng, idx_card)
        reveal_for_all(eng, attr)
        eng.execute(end_discussion_action)

        eliminated = vote_out_any(eng)
        print(f"Eliminated player: {eliminated}")

        # Проверяем не перешли ли мы в Phase2
        if eng._phase is GamePhase.PHASE2:
            break

    # Должны перейти в PHASE2
    assert eng._phase is GamePhase.PHASE2
    assert len(game.team_in_bunker) > 0
    assert len(game.team_outside) > 0
    print(
        f"Phase2 started! Bunker team: {len(game.team_in_bunker)}, Outside team: {len(game.team_outside)}"
    )

    # ===============  ФАЗА 2 ===============
    print("Starting Phase 2...")

    # Проверяем начальное состояние Phase2
    view = eng.view()
    phase2_data = view["phase2"]
    assert phase2_data["current_team"] == "outside"
    assert phase2_data["bunker_hp"] > 0

    # Отладочная информация
    print(f"Initial Phase2 state:")
    print(f"  Current player: {phase2_data.get('current_player')}")
    print(f"  Available actions: {phase2_data.get('available_actions')}")
    print(
        f"  Team states: bunker={list(game.team_in_bunker)}, outside={list(game.team_outside)}"
    )

    # Убедимся что у нас есть игроки
    assert (
        phase2_data["current_player"] is not None
    ), f"No current player! Team states: {eng._phase2_engine._team_states}"
    assert len(phase2_data["available_actions"]) > 0

    max_iterations = 200
    iteration = 0

    while eng._phase is GamePhase.PHASE2 and iteration < max_iterations:
        iteration += 1
        view = eng.view()
        phase2_data = view["phase2"]
        available_actions = eng._get_available_actions()

        print(
            f"Iteration {iteration}: Round {phase2_data['round']}, Team: {phase2_data['current_team']}, HP: {phase2_data['bunker_hp']}"
        )
        print(f"  Current player: {phase2_data.get('current_player')}")
        print(f"  Available engine actions: {available_actions}")
        print(f"  Action queue length: {len(phase2_data.get('action_queue', []))}")
        print(f"  Can process: {phase2_data.get('can_process_actions')}")
        print(f"  Team turn complete: {phase2_data.get('team_turn_complete')}")

        # Если есть кризис - разрешаем его
        if phase2_data.get("current_crisis"):
            print(f"Resolving crisis: {phase2_data['current_crisis']['name']}")
            crisis_action = GameAction(
                type=ActionType.RESOLVE_CRISIS, payload={"result": "bunker_win"}
            )
            eng.execute(crisis_action)
            continue

        # Если можем обработать действия - обрабатываем
        if "process_action" in available_actions:
            print("Processing queued actions...")
            process_action = GameAction(type=ActionType.PROCESS_ACTION)
            eng.execute(process_action)
            continue

        # Если ход команды завершен - завершаем его
        if "finish_team_turn" in available_actions:
            print(f"Finishing turn for team {phase2_data['current_team']}")
            finish_action = GameAction(type=ActionType.FINISH_TEAM_TURN)
            eng.execute(finish_action)
            continue

        # Если есть текущий игрок - делаем действие
        if "make_action" in available_actions:
            current_player = phase2_data.get("current_player")
            available_player_actions = phase2_data.get("available_actions", [])

            if current_player and available_player_actions:
                # Выбираем действие в зависимости от команды
                if phase2_data["current_team"] == "outside":
                    action_id = "attack_bunker"
                else:
                    action_id = "repair_bunker"

                # Проверяем что действие доступно
                available_ids = [a["id"] for a in available_player_actions]
                if action_id not in available_ids:
                    action_id = available_ids[0]

                print(f"Player {current_player} performing {action_id}")

                player_action = GameAction(
                    type=ActionType.MAKE_ACTION,
                    payload={
                        "player_id": current_player,
                        "action_id": action_id,
                        "params": {},
                    },
                )
                eng.execute(player_action)
                continue

        # Если мы здесь - что-то пошло не так
        print(f"WARNING: No available actions at iteration {iteration}")
        print(f"Available actions: {available_actions}")
        break

    # ===============  ПРОВЕРКИ РЕЗУЛЬТАТА ===============
    print(f"Game finished after {iteration} iterations")

    # Игра должна завершиться
    assert eng._phase is GamePhase.FINISHED
    assert eng.game.winner in ("outside", "bunker")

    final_view = eng.view()
    final_phase2 = final_view["phase2"]

    print(
        f"Final result: Winner = {final_phase2['winner']}, Bunker HP = {final_phase2['bunker_hp']}"
    )
    print("✓ Phase2 test completed successfully!")


def test_phase2_action_queue_mechanics(
    game_data: GameData, initializer: GameInitializer
):
    """Тест механики очереди действий и группировки"""
    game = make_game(4)
    eng = GameEngine(game, initializer, game_data)

    # НЕ запускаем полную игру, а сразу настраиваем Phase2
    # Получаем список игроков
    player_ids = list(game.players.keys())
    print(f"Available players: {player_ids}")

    # Принудительно устанавливаем команды ДО инициализации Phase2
    bunker_players = player_ids[:2]
    outside_players = player_ids[2:]

    print(f"Setting up teams: bunker={bunker_players}, outside={outside_players}")

    # Устанавливаем команды в игре
    game.team_outside = set(outside_players)
    game.team_in_bunker = set(bunker_players)

    # Устанавливаем что некоторые игроки исключены
    game.eliminated_ids = set(outside_players)

    # Создаем персонажей вручную - ПОЛНАЯ ВЕРСИЯ
    from bunker.domain.models.traits import Trait

    class MockCharacter:
        def __init__(self):
            self.traits = {
                "profession": Trait("Test Profession", add={"СИЛ": 5, "ТЕХ": 3}),
                "hobby": Trait("Test Hobby", add={"ИНТ": 2}),
                "health": Trait("Test Health", add={"ЗДР": 1}),
                "item": Trait("Test Item", add={"ТЕХ": 1}),
                "phobia": Trait("Test Phobia"),
                "personality": Trait("Test Personality", add={"ХАР": 2}),
                "secret": Trait("Test Secret", add={"ЭМП": 1}),
            }
            self.revealed = []

        def aggregate_stats(self):
            return {"СИЛ": 5, "ТЕХ": 4, "ИНТ": 2, "ЗДР": 1, "ХАР": 2, "ЭМП": 1}

        def to_public_dict(self):
            """Метод для совместимости с Game.to_dict()"""
            return {
                attr: (self.traits[attr].name if attr in self.revealed else None)
                for attr in self.traits.keys()
            }

        def reveal(self, attr: str):
            """Метод для раскрытия атрибутов"""
            if attr in self.traits and attr not in self.revealed:
                self.revealed.append(attr)

        def is_revealed(self, attr: str) -> bool:
            """Проверить раскрыт ли атрибут"""
            return attr in self.revealed

        @property
        def reveal_order(self):
            """Порядок раскрытия атрибутов"""
            return list(self.traits.keys())

    for pid in player_ids:
        game.characters[pid] = MockCharacter()

    # Теперь инициализируем Phase2
    eng._init_phase2()

    assert eng._phase is GamePhase.PHASE2

    # Проверяем что команда снаружи ходит первой
    view = eng.view()
    assert view["phase2"]["current_team"] == "outside"

    # Отладочная информация
    print(f"Current team: {view['phase2']['current_team']}")
    print(f"Current player: {view['phase2']['current_player']}")

    # Первый игрок делает действие
    current_player = view["phase2"]["current_player"]
    assert (
        current_player is not None
    ), f"No current player! Outside team: {outside_players}"
    assert (
        current_player in outside_players
    ), f"Current player {current_player} not in outside team {outside_players}"

    # Проверяем доступные действия
    available_actions = view["phase2"]["available_actions"]
    assert len(available_actions) > 0, "No available actions for outside team"

    # Выбираем первое доступное действие
    action_id = available_actions[0]["id"]

    eng.execute(
        GameAction(
            type=ActionType.MAKE_ACTION,
            payload={"player_id": current_player, "action_id": action_id, "params": {}},
        )
    )

    # Проверяем что действие добавилось в очередь
    view = eng.view()
    assert len(view["phase2"]["action_queue"]) == 1
    assert view["phase2"]["action_queue"][0]["action_type"] == action_id
    assert len(view["phase2"]["action_queue"][0]["participants"]) == 1
    assert view["phase2"]["action_queue"][0]["participants"][0] == current_player

    # Второй игрок делает то же действие (если есть)
    current_player = view["phase2"]["current_player"]
    if current_player:  # Если есть еще игроки в команде
        print(f"Second player {current_player} making action {action_id}")

        eng.execute(
            GameAction(
                type=ActionType.MAKE_ACTION,
                payload={
                    "player_id": current_player,
                    "action_id": action_id,
                    "params": {},
                },
            )
        )

        # Проверяем группировку - должно быть все еще 1 действие, но с 2 участниками
        view = eng.view()
        assert len(view["phase2"]["action_queue"]) == 1
        assert len(view["phase2"]["action_queue"][0]["participants"]) == 2
        print("✓ Action grouping works correctly!")

    print("✓ Action queue mechanics test completed!")


def test_phase2_crisis_mechanics(game_data: GameData, initializer: GameInitializer):
    """Тест механики кризисов"""
    game = make_game(4)
    eng = GameEngine(game, initializer, game_data)

    # Получаем список игроков
    player_ids = list(game.players.keys())
    bunker_players = player_ids[:2]
    outside_players = player_ids[2:]

    # Устанавливаем команды
    game.team_outside = set(outside_players)
    game.team_in_bunker = set(bunker_players)
    game.eliminated_ids = set(outside_players)

    # Создаем персонажей вручную - ПОЛНАЯ ВЕРСИЯ
    from bunker.domain.models.traits import Trait

    class MockCharacter:
        def __init__(self):
            self.traits = {
                "profession": Trait("Test Profession", add={"СИЛ": 1, "ТЕХ": 1}),
                "hobby": Trait("Test Hobby", add={"ИНТ": 1}),
                "health": Trait("Test Health", add={"ЗДР": 1}),
                "item": Trait("Test Item", add={"ТЕХ": 1}),
                "phobia": Trait("Test Phobia"),
                "personality": Trait("Test Personality", add={"ХАР": 1}),
                "secret": Trait("Test Secret", add={"ЭМП": 1}),
            }
            self.revealed = []

        def aggregate_stats(self):
            return {"СИЛ": 1, "ТЕХ": 2, "ИНТ": 1, "ЗДР": 1, "ХАР": 1, "ЭМП": 1}

        def to_public_dict(self):
            """Метод для совместимости с Game.to_dict()"""
            return {
                attr: (self.traits[attr].name if attr in self.revealed else None)
                for attr in self.traits.keys()
            }

        def reveal(self, attr: str):
            """Метод для раскрытия атрибутов"""
            if attr in self.traits and attr not in self.revealed:
                self.revealed.append(attr)

        def is_revealed(self, attr: str) -> bool:
            """Проверить раскрыт ли атрибут"""
            return attr in self.revealed

        @property
        def reveal_order(self):
            """Порядок раскрытия атрибутов"""
            return list(self.traits.keys())

    for pid in player_ids:
        game.characters[pid] = MockCharacter()

    # Инициализируем Phase2
    eng._init_phase2()

    # Переключаемся на команду бункера
    eng.game.phase2_current_team = "bunker"

    # Сбрасываем индекс текущего игрока для команды бункера
    bunker_team = eng._phase2_engine._team_states["bunker"]
    bunker_team.current_player_index = 0

    view = eng.view()
    current_player = view["phase2"]["current_player"]

    assert (
        current_player is not None
    ), f"No current player in bunker team! Players: {bunker_players}"
    assert current_player in bunker_players

    # Получаем доступные действия для команды бункера
    available_actions = view["phase2"]["available_actions"]
    assert len(available_actions) > 0, "No available actions for bunker team"

    # Выбираем действие которое может вызвать кризис при неудаче
    action_id = available_actions[0]["id"]  # Используем первое доступное

    eng.execute(
        GameAction(
            type=ActionType.MAKE_ACTION,
            payload={"player_id": current_player, "action_id": action_id, "params": {}},
        )
    )

    # Завершаем ход команды если нужно
    view = eng.view()
    if view["phase2"]["team_turn_complete"]:
        if view["phase2"]["can_process_actions"]:
            # Обрабатываем действие (может вызвать кризис при неудаче)
            eng.execute(GameAction(type=ActionType.PROCESS_ACTION))

            view = eng.view()
            # Если есть кризис - разрешаем его
            if view["phase2"]["current_crisis"]:
                print(f"Crisis triggered: {view['phase2']['current_crisis']['name']}")

                # Тестируем разрешение кризиса
                eng.execute(
                    GameAction(
                        type=ActionType.RESOLVE_CRISIS,
                        payload={"result": "bunker_lose"},
                    )
                )

                # Кризис должен исчезнуть
                view = eng.view()
                assert view["phase2"]["current_crisis"] is None
                print("✓ Crisis resolved correctly!")
            else:
                print("No crisis triggered (action succeeded)")

    print("✓ Crisis mechanics test completed!")


def create_mock_character(stats=None):
    """Создать полноценный мок-персонажа для тестов"""
    from bunker.domain.models.traits import Trait

    default_stats = {"СИЛ": 3, "ТЕХ": 2, "ИНТ": 4, "ЗДР": 2, "ХАР": 3, "ЭМП": 2}
    if stats:
        default_stats.update(stats)

    class MockCharacter:
        def __init__(self):
            self.traits = {
                "profession": Trait("Mock Profession"),
                "hobby": Trait("Mock Hobby"),
                "health": Trait("Mock Health"),
                "item": Trait("Mock Item"),
                "phobia": Trait("Mock Phobia"),
                "personality": Trait("Mock Personality"),
                "secret": Trait("Mock Secret"),
            }
            self.revealed = []

        def aggregate_stats(self):
            return default_stats.copy()

        def to_public_dict(self):
            """Метод для совместимости с Game.to_dict()"""
            return {
                attr: (self.traits[attr].name if attr in self.revealed else None)
                for attr in self.traits.keys()
            }

        def reveal(self, attr: str):
            """Метод для раскрытия атрибутов"""
            if attr in self.traits and attr not in self.revealed:
                self.revealed.append(attr)

        def is_revealed(self, attr: str) -> bool:
            """Проверить раскрыт ли атрибут"""
            return attr in self.revealed

        @property
        def reveal_order(self):
            """Порядок раскрытия атрибутов"""
            return list(self.traits.keys())

    return MockCharacter()
