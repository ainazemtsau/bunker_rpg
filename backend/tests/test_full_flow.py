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
    """Полный тест игрового флоу включая Phase2 с мини-играми"""
    game = make_game(8)
    eng = GameEngine(game, initializer, game_data)

    # ===============  ФАЗА 1 ===============
    print("Starting Phase 1...")

    start_action = GameAction(type=ActionType.START_GAME)
    eng.execute(start_action)
    assert eng._phase is GamePhase.BUNKER
    assert len(game.characters) == 8

    # Быстро доходим до Phase2 - исключаем больше игроков
    attrs = ["profession", "hobby", "item", "health", "phobia", "personality"]
    for idx_card, attr in enumerate(attrs, start=1):
        print(f"Round {idx_card}: revealing {attr}")
        print(
            f"  Before round - Alive: {len(game.alive_ids())}, Eliminated: {len(game.eliminated_ids)}"
        )

        open_card(eng, idx_card)
        reveal_for_all(eng, attr)
        eng.execute(GameAction(type=ActionType.END_DISCUSSION))

        if idx_card > 1:  # Начинаем голосовать со второго раунда
            eliminated = vote_out_any(eng)
            print(f"  Eliminated player: {eliminated}")
            print(
                f"  After round - Alive: {len(game.alive_ids())}, Eliminated: {len(game.eliminated_ids)}"
            )

        # Проверяем условие перехода
        alive_count = len(game.alive_ids())
        eliminated_count = len(game.eliminated_ids)
        attr_count = game.attr_index

        print(
            f"  Transition check: alive({alive_count}) <= eliminated({eliminated_count}) or attr_index({attr_count}) >= 7"
        )

        if eng._phase is GamePhase.PHASE2:
            print(f"  -> Transitioned to Phase2!")
            break

    # Если все еще не в Phase2 - принудительно переходим
    if eng._phase is not GamePhase.PHASE2:
        print(f"Forcing transition to Phase2...")
        print(
            f"Current state: alive={len(game.alive_ids())}, eliminated={len(game.eliminated_ids())}, attr_index={game.attr_index}"
        )

        # Принудительно исключаем игроков до тех пор пока не будет <= половины
        while len(game.alive_ids()) > len(game.eliminated_ids):
            target = game.alive_ids()[0]
            game.eliminated_ids.add(target)
            game.shuffle_turn_order()
            print(
                f"  Force eliminated: {target}, now alive={len(game.alive_ids())}, eliminated={len(game.eliminated_ids())}"
            )

        # Принудительно инициализируем Phase2
        eng._init_phase2()

    assert eng._phase is GamePhase.PHASE2, f"Expected Phase2, got {eng._phase}"

    print(
        f"Phase2 started! Bunker team: {len(game.team_in_bunker)}, Outside team: {len(game.team_outside)}"
    )

    # ===============  ФАЗА 2 ===============
    print("Starting Phase 2...")

    max_rounds = 5
    rounds_completed = 0
    actions_executed = 0
    crises_encountered = 0

    while eng._phase is GamePhase.PHASE2 and rounds_completed < max_rounds:
        view = eng.view()
        phase2_data = view["phase2"]

        current_round = phase2_data["round"]
        if current_round > rounds_completed:
            rounds_completed = current_round
            print(f"\n=== ROUND {current_round} ===")

        print(
            f"Team: {phase2_data['current_team']}, HP: {phase2_data['bunker_hp']}, Morale: {phase2_data['morale']}, Supplies: {phase2_data['supplies']}"
        )

        # Обработка кризисов с проверкой мини-игр
        if phase2_data.get("current_crisis"):
            crisis = phase2_data["current_crisis"]
            crises_encountered += 1
            print(f"Crisis {crises_encountered}: {crisis['name']}")

            # НОВАЯ ПРОВЕРКА: Проверяем наличие мини-игры
            assert "mini_game" in crisis, "Crisis should have mini_game data"

            if crisis["mini_game"]:
                mini_game = crisis["mini_game"]
                print(f"  Mini-game: {mini_game['name']}")
                print(f"  Rules: {mini_game['rules'][:50]}...")  # Первые 50 символов

                # Проверяем структуру мини-игры
                assert "id" in mini_game, "Mini-game should have ID"
                assert "name" in mini_game, "Mini-game should have name"
                assert "rules" in mini_game, "Mini-game should have rules"
                assert (
                    len(mini_game["rules"]) > 0
                ), "Mini-game rules should not be empty"

                print(f"  ✓ Mini-game data is valid")
            else:
                print(f"  WARNING: No mini-game found for crisis {crisis['id']}")

            # Случайно выбираем результат кризиса
            import random

            crisis_result = random.choice(["bunker_win", "bunker_lose"])
            print(f"  Crisis result: {crisis_result}")

            eng.execute(
                GameAction(
                    type=ActionType.RESOLVE_CRISIS, payload={"result": crisis_result}
                )
            )
            continue

        # Обработка очереди действий
        if phase2_data.get("can_process_actions"):
            print("Processing actions...")
            eng.execute(GameAction(type=ActionType.PROCESS_ACTION))
            continue

        # Завершение хода команды
        if (
            phase2_data.get("team_turn_complete")
            and len(phase2_data.get("action_queue", [])) == 0
        ):
            print(f"Finishing turn for {phase2_data['current_team']}")
            eng.execute(GameAction(type=ActionType.FINISH_TEAM_TURN))
            continue

        # Ход игрока
        current_player = phase2_data.get("current_player")
        if current_player:
            available_actions = phase2_data.get("available_actions", [])

            if not available_actions:
                print(
                    f"ERROR: No actions for {current_player} in team {phase2_data['current_team']}"
                )
                eng.execute(GameAction(type=ActionType.FINISH_TEAM_TURN))
                continue

            # Выбираем действие
            if phase2_data["current_team"] == "outside":
                # Команда снаружи атакует или саботирует
                preferred_actions = [
                    "attack_bunker",
                    "sabotage_systems",
                    "psychological_warfare",
                ]
            else:
                # Команда в бункере ремонтирует или ищет припасы
                preferred_actions = ["repair_bunker", "boost_morale", "search_supplies"]

                # Если есть активные статусы - пытаемся их устранить
                if phase2_data.get("active_statuses"):
                    if "fire" in phase2_data["active_statuses"]:
                        preferred_actions.insert(0, "extinguish_fire")

                # Если есть игроки с фобиями - пытаемся лечить
                if phase2_data.get("active_phobias"):
                    preferred_actions.insert(0, "treat_phobia")

            # Находим первое доступное действие из предпочтительных
            action_id = None
            available_ids = [a["id"] for a in available_actions]

            for preferred in preferred_actions:
                if preferred in available_ids:
                    action_id = preferred
                    break

            # Если не нашли предпочтительное - берем первое доступное
            if not action_id and available_actions:
                action_id = available_actions[0]["id"]

            if action_id:
                print(f"Player {current_player} -> {action_id}")

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
                actions_executed += 1

                # Проверяем не завершилась ли игра
                if eng._phase is GamePhase.FINISHED:
                    break
        else:
            print("ERROR: No current player")
            break

    # ===============  ПРОВЕРКИ РЕЗУЛЬТАТА ===============
    print(
        f"\nGame finished after {rounds_completed} rounds, {actions_executed} actions, {crises_encountered} crises"
    )

    # Игра должна завершиться
    assert eng._phase is GamePhase.FINISHED, f"Expected FINISHED, got {eng._phase}"
    assert eng.game.winner in (
        "outside",
        "bunker",
    ), f"Invalid winner: {eng.game.winner}"

    # Должны быть выполнены действия
    assert (
        actions_executed > 0
    ), f"No actions were executed! Actions: {actions_executed}"

    # Проверяем что встретили кризисы с мини-играми
    print(f"Total crises encountered: {crises_encountered}")
    if crises_encountered > 0:
        print("✓ Crisis and mini-game system tested")

    print(
        f"✓ Phase2 with mini-games test completed! Winner: {eng.game.winner}, Actions: {actions_executed}, Crises: {crises_encountered}"
    )

    final_view = eng.view()
    final_phase2 = final_view["phase2"]

    initial_config = game_data.phase2_config.game_settings
    initial_hp = initial_config.get("starting_bunker_hp", 5)
    initial_morale = initial_config.get("starting_morale", 6)
    initial_supplies = initial_config.get("starting_supplies", 5)

    print(f"Resource changes:")
    print(f"  HP: {initial_hp} -> {final_phase2['bunker_hp']}")
    print(f"  Morale: {initial_morale} -> {final_phase2['morale']}")
    print(f"  Supplies: {initial_supplies} -> {final_phase2['supplies']}")

    # Хотя бы один ресурс должен измениться
    resources_changed = (
        final_phase2["bunker_hp"] != initial_hp
        or final_phase2["morale"] != initial_morale
        or final_phase2["supplies"] != initial_supplies
    )
    assert resources_changed, "No resources were changed during the game!"

    # Проверяем что объекты бункера есть
    assert len(final_phase2.get("bunker_objects", {})) > 0, "No bunker objects found!"

    # Проверяем что статы команд рассчитаны
    assert "team_stats" in final_phase2, "Team stats not calculated!"
    assert "bunker" in final_phase2["team_stats"], "Bunker team stats missing!"
    assert "outside" in final_phase2["team_stats"], "Outside team stats missing!"


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


def test_debug_phase2_simple():
    """Отладочный тест для понимания проблем"""
    from pathlib import Path
    from bunker.core.loader import GameData
    from bunker.domain.game_init import GameInitializer

    DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")
    game_data = GameData(root=DATA_DIR)
    initializer = GameInitializer(game_data)

    # Простая настройка
    game = make_game(4)
    eng = GameEngine(game, initializer, game_data)

    # Быстро до Phase2
    eng.execute(GameAction(type=ActionType.START_GAME))

    # Принудительно устанавливаем команды ПРАВИЛЬНО
    player_ids = list(game.players.keys())
    game.team_outside = set(player_ids[:2])
    game.team_in_bunker = set(player_ids[2:])

    # Также устанавливаем eliminated_ids для совместимости
    game.eliminated_ids = set(player_ids[:2])  # первые 2 исключены

    print(
        f"Before init - Outside: {list(game.team_outside)}, Bunker: {list(game.team_in_bunker)}"
    )
    print(f"Eliminated: {list(game.eliminated_ids)}, Alive: {game.alive_ids()}")

    # Инициализируем Phase2
    eng._init_phase2()

    print(
        f"After init - Outside: {list(game.team_outside)}, Bunker: {list(game.team_in_bunker)}"
    )

    print(f"\n=== INITIAL STATE ===")
    view = eng.view()
    p2 = view["phase2"]
    print(f"HP: {p2['bunker_hp']}, Morale: {p2['morale']}, Supplies: {p2['supplies']}")
    print(f"Current team: {p2['current_team']}")
    print(f"Current player: {p2['current_player']}")
    print(f"Available actions: {[a['id'] for a in p2['available_actions']]}")

    assert p2["current_player"] is not None, "No current player!"
    assert len(p2["available_actions"]) > 0, "No available actions!"

    # Попробуем одно действие
    action_id = p2["available_actions"][0]["id"]
    print(f"\n=== EXECUTING ACTION: {action_id} ===")

    eng.execute(
        GameAction(
            type=ActionType.MAKE_ACTION,
            payload={
                "player_id": p2["current_player"],
                "action_id": action_id,
                "params": {},
            },
        )
    )

    view = eng.view()
    p2 = view["phase2"]
    print(
        f"After action - HP: {p2['bunker_hp']}, Morale: {p2['morale']}, Supplies: {p2['supplies']}"
    )
    print(f"Can process actions: {p2['can_process_actions']}")
    print(f"Action queue: {p2['action_queue']}")

    if p2["can_process_actions"]:
        print(f"\n=== PROCESSING ACTION ===")
        eng.execute(GameAction(type=ActionType.PROCESS_ACTION))

        view = eng.view()
        p2 = view["phase2"]
        print(
            f"After processing - HP: {p2['bunker_hp']}, Morale: {p2['morale']}, Supplies: {p2['supplies']}"
        )
        print(f"Phase: {eng._phase}")
        print(f"Winner: {p2['winner']}")

    # Попробуем принудительно обнулить ресурсы
    print(f"\n=== FORCING ZERO RESOURCES ===")
    original_hp = eng.game.phase2_bunker_hp
    original_morale = eng.game.phase2_morale
    original_supplies = eng.game.phase2_supplies

    eng.game.phase2_bunker_hp = 0
    eng.game.phase2_morale = 0
    eng.game.phase2_supplies = 0

    print(f"Set HP: {original_hp} -> 0")
    print(f"Set Morale: {original_morale} -> 0")
    print(f"Set Supplies: {original_supplies} -> 0")

    # Проверим условия победы
    print(f"Manually checking victory conditions...")
    eng._check_phase2_victory()
    print(f"Phase after manual check: {eng._phase}")
    print(f"Winner: {eng.game.winner}")

    if eng._phase2_engine:
        victory = eng._phase2_engine.check_victory_conditions()
        print(f"Victory condition returned: {victory}")

    # Должна быть победа
    assert (
        eng._phase is GamePhase.FINISHED
    ), f"Game should be finished, but phase is {eng._phase}"
    assert (
        eng.game.winner == "outside"
    ), f"Outside team should win, but winner is {eng.game.winner}"

    print("✓ Debug test completed successfully!")
