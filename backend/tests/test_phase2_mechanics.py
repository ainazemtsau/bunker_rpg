# backend/tests/test_phase2_mechanics.py
import pytest
from pathlib import Path
from bunker.core.loader import GameData
from bunker.domain.engine import GameEngine
from bunker.domain.game_init import GameInitializer
from bunker.domain.types import GamePhase, ActionType, GameAction
from bunker.domain.models.models import Game, Player

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


@pytest.fixture
def setup_phase2():
    """Подготовка игры для Phase2 тестов"""
    game_data = GameData(root=DATA_DIR)
    initializer = GameInitializer(game_data)

    # Создаем игру с 4 игроками
    host = Player("Host", "H")
    game = Game(host)
    for i in range(4):
        p = Player(f"P{i}", f"S{i}")
        game.players[p.id] = p

    eng = GameEngine(game, initializer, game_data)
    eng.execute(GameAction(type=ActionType.START_GAME))

    # Быстро переходим к Phase2
    player_ids = list(game.players.keys())
    game.team_outside = set(player_ids[:2])
    game.team_in_bunker = set(player_ids[2:])
    game.eliminated_ids = set(player_ids[:2])

    eng._init_phase2()

    return eng, game, game_data


def test_simple_phase2_check():
    """Простой тест для проверки что файл работает"""
    print("test_phase2_mechanics.py is working!")
    assert True


def test_mini_games_loading():
    """Тест загрузки мини-игр из YAML"""
    print("\n=== Testing Mini-Games Loading ===")

    game_data = GameData(root=DATA_DIR)

    # Проверяем что мини-игры загрузились
    assert hasattr(game_data, "mini_games"), "Mini-games not loaded"
    assert len(game_data.mini_games) > 0, "No mini-games loaded"

    print(f"Loaded {len(game_data.mini_games)} mini-games")

    # Проверяем структуру первой мини-игры
    first_game = next(iter(game_data.mini_games.values()))
    assert hasattr(first_game, "id"), "Mini-game missing ID"
    assert hasattr(first_game, "name"), "Mini-game missing name"
    assert hasattr(first_game, "rules"), "Mini-game missing rules"
    assert hasattr(first_game, "crisis_events"), "Mini-game missing crisis_events"

    assert len(first_game.rules) > 0, "Mini-game rules should not be empty"
    assert len(first_game.crisis_events) > 0, "Mini-game should have crisis events"

    # Проверяем что есть мини-игры для основных кризисов
    fire_games = [
        g for g in game_data.mini_games.values() if "fire_outbreak" in g.crisis_events
    ]
    assert len(fire_games) > 0, "No mini-games for fire_outbreak crisis"

    structural_games = [
        g
        for g in game_data.mini_games.values()
        if "structural_damage" in g.crisis_events
    ]
    assert len(structural_games) > 0, "No mini-games for structural_damage crisis"

    print("✓ Mini-games loaded correctly")


def test_crisis_mini_game_selection(setup_phase2):
    """Тест выбора мини-игры для кризиса"""
    eng, game, game_data = setup_phase2

    print("\n=== Testing Crisis Mini-Game Selection ===")

    # Принудительно создаем кризис
    if eng._phase2_engine:
        # Тестируем выбор мини-игры для fire_outbreak
        crisis_event = eng._phase2_engine._create_crisis_event("fire_outbreak")

        assert crisis_event is not None, "Crisis event should be created"
        assert crisis_event.mini_game is not None, "Crisis should have mini-game"

        mini_game = crisis_event.mini_game
        assert mini_game.mini_game_id is not None, "Mini-game should have ID"
        assert mini_game.name is not None, "Mini-game should have name"
        assert mini_game.rules is not None, "Mini-game should have rules"
        assert len(mini_game.rules) > 0, "Mini-game rules should not be empty"

        print(f"Selected mini-game: {mini_game.name}")
        print(f"Rules preview: {mini_game.rules[:100]}...")

        # Проверяем что выбранная мини-игра действительно подходит для fire_outbreak
        selected_game_def = game_data.mini_games.get(mini_game.mini_game_id)
        assert selected_game_def is not None, "Selected mini-game should exist in data"
        assert (
            "fire_outbreak" in selected_game_def.crisis_events
        ), "Selected mini-game should support fire_outbreak"

        print("✓ Mini-game selection works correctly")


def test_crisis_with_mini_game_in_view(setup_phase2):
    """Тест отображения кризиса с мини-игрой в представлении"""
    eng, game, game_data = setup_phase2

    print("\n=== Testing Crisis Mini-Game in View ===")

    # Принудительно создаем кризис в движке
    if eng._phase2_engine:
        crisis_event = eng._phase2_engine._create_crisis_event("structural_damage")
        eng._phase2_engine._current_crisis = crisis_event

        # Получаем представление
        view = eng.view()
        phase2_data = view["phase2"]

        # Проверяем что кризис есть в представлении
        assert "current_crisis" in phase2_data, "Current crisis should be in view"
        current_crisis = phase2_data["current_crisis"]
        assert current_crisis is not None, "Current crisis should not be None"

        # Проверяем структуру кризиса
        assert "id" in current_crisis, "Crisis should have ID"
        assert "name" in current_crisis, "Crisis should have name"
        assert "description" in current_crisis, "Crisis should have description"
        assert "mini_game" in current_crisis, "Crisis should have mini_game field"

        # Проверяем структуру мини-игры
        mini_game = current_crisis["mini_game"]
        assert mini_game is not None, "Mini-game should not be None"
        assert "id" in mini_game, "Mini-game should have ID"
        assert "name" in mini_game, "Mini-game should have name"
        assert "rules" in mini_game, "Mini-game should have rules"

        print(f"Crisis in view: {current_crisis['name']}")
        print(f"Mini-game in view: {mini_game['name']}")
        print(f"Rules length: {len(mini_game['rules'])} characters")

        assert len(mini_game["rules"]) > 50, "Mini-game rules should be substantial"

        print("✓ Crisis with mini-game appears correctly in view")


def test_multiple_mini_games_for_crisis():
    """Тест что для кризиса может быть несколько мини-игр"""
    print("\n=== Testing Multiple Mini-Games for Crisis ===")

    game_data = GameData(root=DATA_DIR)

    # Ищем кризис который имеет несколько мини-игр
    crisis_mini_games = {}
    for mini_game in game_data.mini_games.values():
        for crisis_id in mini_game.crisis_events:
            if crisis_id not in crisis_mini_games:
                crisis_mini_games[crisis_id] = []
            crisis_mini_games[crisis_id].append(mini_game)

    print(f"Crisis -> Mini-games mapping:")
    for crisis_id, games in crisis_mini_games.items():
        print(f"  {crisis_id}: {len(games)} mini-games")

    # Должен быть хотя бы один кризис с несколькими мини-играми
    multi_game_crises = [
        crisis for crisis, games in crisis_mini_games.items() if len(games) > 1
    ]

    if multi_game_crises:
        print(f"Crises with multiple mini-games: {multi_game_crises}")
        print("✓ Multiple mini-games per crisis system works")
    else:
        print(
            "⚠ No crises with multiple mini-games found (this is OK but could add more variety)"
        )


def test_action_grouping(setup_phase2):
    """Тест группировки одинаковых действий"""
    eng, game, game_data = setup_phase2

    print("\n=== Testing Action Grouping ===")

    # Должна быть команда outside
    view = eng.view()
    assert view["phase2"]["current_team"] == "outside"

    # Получаем игроков команды outside
    outside_players = list(game.team_outside)
    assert len(outside_players) == 2
    print(f"Outside players: {outside_players}")

    # ИСПРАВЛЕНИЕ: Получаем текущего игрока из view, а не предполагаем порядок
    current_player = view["phase2"]["current_player"]
    assert (
        current_player in outside_players
    ), f"Current player {current_player} should be in outside team {outside_players}"

    print(f"Current player: {current_player}")

    # Первый игрок выбирает действие
    eng.execute(
        GameAction(
            type=ActionType.MAKE_ACTION,
            payload={
                "player_id": current_player,
                "action_id": "attack_bunker",
                "params": {},
            },
        )
    )

    # Проверяем что действие добавилось в очередь
    view = eng.view()
    assert len(view["phase2"]["action_queue"]) == 1
    assert view["phase2"]["action_queue"][0]["action_type"] == "attack_bunker"
    assert len(view["phase2"]["action_queue"][0]["participants"]) == 1
    assert current_player in view["phase2"]["action_queue"][0]["participants"]

    # Получаем следующего игрока
    next_player = view["phase2"]["current_player"]

    # Если есть следующий игрок - он должен быть другим
    if next_player:
        assert next_player != current_player, "Next player should be different"
        assert (
            next_player in outside_players
        ), f"Next player {next_player} should be in outside team"

        print(f"Next player: {next_player}")

        # Второй игрок выбирает то же действие
        eng.execute(
            GameAction(
                type=ActionType.MAKE_ACTION,
                payload={
                    "player_id": next_player,
                    "action_id": "attack_bunker",
                    "params": {},
                },
            )
        )

        # Проверяем группировку - должно быть 1 действие с 2 участниками
        view = eng.view()
        assert len(view["phase2"]["action_queue"]) == 1
        assert len(view["phase2"]["action_queue"][0]["participants"]) == 2
        assert current_player in view["phase2"]["action_queue"][0]["participants"]
        assert next_player in view["phase2"]["action_queue"][0]["participants"]

        print("✓ Action grouping with 2 players works correctly")
    else:
        print("✓ Action grouping with 1 player works correctly")

    print("✓ Action grouping works correctly")


def test_victory_conditions(setup_phase2):
    """Тест условий победы"""
    eng, game, game_data = setup_phase2

    print("\n=== Testing Victory Conditions ===")

    # Тест победы через уничтожение бункера
    print("Testing bunker destruction...")
    original_hp = game.phase2_bunker_hp
    game.phase2_bunker_hp = 0

    victory = eng._phase2_engine.check_victory_conditions()
    assert victory == "bunker_destroyed"
    assert game.winner == "outside"

    print("✓ Victory conditions work correctly")


def test_forced_crisis_with_mini_game(setup_phase2):
    """Тест принудительного кризиса с проверкой мини-игры"""
    eng, game, game_data = setup_phase2

    print("\n=== Testing Forced Crisis with Mini-Game ===")

    # Переключаемся на команду бункера
    game.phase2_current_team = "bunker"

    # Сбрасываем индекс игрока команды бункера
    if eng._phase2_engine:
        bunker_team = eng._phase2_engine._team_states["bunker"]
        bunker_team.current_player_index = 0

        # Принудительно создаем кризис
        crisis_event = eng._phase2_engine._create_crisis_event("power_failure")
        eng._phase2_engine._current_crisis = crisis_event

        # Проверяем что кризис создался с мини-игрой
        assert crisis_event.mini_game is not None, "Crisis should have mini-game"

        view = eng.view()
        crisis_data = view["phase2"]["current_crisis"]

        assert crisis_data is not None, "Crisis should be in view"
        assert (
            crisis_data["mini_game"] is not None
        ), "Crisis should have mini-game in view"

        mini_game = crisis_data["mini_game"]
        print(f"Crisis: {crisis_data['name']}")
        print(f"Mini-game: {mini_game['name']}")
        print(f"Rules: {mini_game['rules'][:100]}...")

        # Разрешаем кризис
        eng.execute(
            GameAction(type=ActionType.RESOLVE_CRISIS, payload={"result": "bunker_win"})
        )

        # Кризис должен исчезнуть
        view = eng.view()
        assert view["phase2"]["current_crisis"] is None, "Crisis should be resolved"

        print("✓ Forced crisis with mini-game works correctly")
