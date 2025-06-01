import pytest
from pathlib import Path
import random

from bunker.core.loader import GameData
from bunker.domain.engine import GameEngine
from bunker.domain.game_init import GameInitializer
from bunker.domain.types import GamePhase, ActionType, GameAction
from bunker.domain.models.models import Game, Player
from bunker.domain.models.traits import Trait
from bunker.domain.models.character import Character
from bunker.domain.phase2.types import CrisisResult

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")
TEST_DATA_DIR = Path(__file__).parent / "data"


class CustomGameData(GameData):  # ← ПЕРЕИМЕНОВАНО для избежания предупреждения pytest
    """Тестовый GameData с переопределенным конфигом"""

    def __init__(self, root: Path | str):
        super().__init__(root)
        # Переопределяем конфиг для тестов если есть
        test_config_file = TEST_DATA_DIR / "phase2_config.yml"
        if test_config_file.exists():
            from bunker.domain.models.phase2_models import Phase2Config

            raw = self.load_any(test_config_file)
            self.phase2_config = Phase2Config.from_raw(raw)
            print(
                f"Using test config: starting_hp={self.phase2_config.game_settings.get('starting_bunker_hp')}, max_hp={self.phase2_config.game_settings.get('max_bunker_hp')}"
            )

        # ← ВАЖНО: Увеличиваем сложность действий для провала
        self._increase_action_difficulty()

    def _increase_action_difficulty(self):
        """Увеличить сложность действий для тестирования провалов"""
        for action in self.phase2_actions.values():
            if action.team == "bunker":
                action.difficulty = 25  # Очень высокая сложность
                print(f"Increased difficulty for {action.id} to {action.difficulty}")

    def load_any(self, path: Path):
        """Метод для загрузки YAML/JSON файлов"""
        import yaml, json

        with path.open(encoding="utf8") as f:
            return (
                yaml.safe_load(f) if path.suffix in {".yml", ".yaml"} else json.load(f)
            )


class FixedRandomForTesting(random.Random):
    """Фиксированный рандом для предсказуемых тестов"""

    def __init__(self, roll_sequence=None, choice_sequence=None):
        super().__init__()
        self.roll_sequence = roll_sequence or []
        self.choice_sequence = choice_sequence or []
        self.roll_index = 0
        self.choice_index = 0

    def randint(self, a, b):
        if self.roll_index < len(self.roll_sequence):
            result = self.roll_sequence[self.roll_index]
            self.roll_index += 1
            print(f"Fixed roll: {result}")
            return result
        return super().randint(a, b)

    def choice(self, sequence):
        if self.choice_index < len(self.choice_sequence):
            choice_item = self.choice_sequence[self.choice_index]
            self.choice_index += 1
            print(f"Fixed choice: {choice_item} from {len(sequence)} options")

            # Если choice_item это строка, ищем в sequence
            for item in sequence:
                if (
                    hasattr(item, "id") and item.id == choice_item
                ) or item == choice_item:
                    return item
            return sequence[0]  # fallback
        return super().choice(sequence)


def create_weak_character(profession="Weak Prof"):
    """Создать ОЧЕНЬ СЛАБОГО персонажа для гарантированного провала"""
    # Делаем все статы 0, чтобы гарантированно провалить действия
    return Character(
        traits={
            "profession": Trait(profession, add={}),  # Никаких бонусов
            "hobby": Trait("Weak Hobby", add={}),
            "health": Trait("Больной", add={"ЗДР": -1}),  # Отрицательные статы
            "item": Trait("Сломанный предмет", add={}),
            "phobia": Trait("Test Phobia"),
            "personality": Trait("Weak Personality", add={}),
            "secret": Trait("Test Secret", add={}),
        }
    )


def create_strong_character(profession="Strong Prof"):
    """Создать сильного персонажа для гарантированного успеха"""
    return Character(
        traits={
            "profession": Trait(
                profession,
                add={"СИЛ": 10, "ТЕХ": 10, "ИНТ": 10, "ЗДР": 10, "ХАР": 10, "ЭМП": 10},
            ),
            "hobby": Trait(
                "Strong Hobby",
                add={"СИЛ": 5, "ТЕХ": 5, "ИНТ": 5, "ЗДР": 5, "ХАР": 5, "ЭМП": 5},
            ),
            "health": Trait("Здоров", add={"ЗДР": 2}),
            "item": Trait("Мощный предмет", add={"ТЕХ": 3}),
            "phobia": Trait("Test Phobia"),
            "personality": Trait("Strong Personality", add={"ХАР": 3}),
            "secret": Trait("Test Secret", add={"ЭМП": 2}),
        }
    )


def setup_full_game_for_success() -> tuple[GameEngine, Game, GameData]:
    """Создать игру с сильными персонажами для тестирования успеха"""
    game_data = CustomGameData(root=DATA_DIR)

    # Понижаем сложность для тестирования успеха
    for action in game_data.phase2_actions.values():
        if action.team == "bunker":
            action.difficulty = 10  # Низкая сложность

    initializer = GameInitializer(game_data)

    # Создаем игру с 4 игроками
    host = Player("Host", "H")
    game = Game(host)

    player_ids = []
    for i in range(4):
        p = Player(f"Player{i}", f"S{i}")
        game.players[p.id] = p
        player_ids.append(p.id)

    # Создаем СИЛЬНЫХ персонажей
    for pid in player_ids:
        game.characters[pid] = create_strong_character()

    # Быстро переходим к Phase2
    eng = GameEngine(game, initializer, game_data)
    eng.execute(GameAction(type=ActionType.START_GAME))

    # Настраиваем команды
    bunker_players = player_ids[:2]
    outside_players = player_ids[2:]

    game.team_in_bunker = set(bunker_players)
    game.team_outside = set(outside_players)
    game.eliminated_ids = set(outside_players)

    # Инициализируем Phase2
    eng._init_phase2()

    return eng, game, game_data


def setup_full_game_for_failure() -> tuple[GameEngine, Game, GameData]:
    """Создать игру со слабыми персонажами для тестирования провала"""
    game_data = CustomGameData(root=DATA_DIR)  # Высокая сложность уже установлена
    initializer = GameInitializer(game_data)

    # Создаем игру с 4 игроками
    host = Player("Host", "H")
    game = Game(host)

    player_ids = []
    for i in range(4):
        p = Player(f"Player{i}", f"S{i}")
        game.players[p.id] = p
        player_ids.append(p.id)

    # Создаем СЛАБЫХ персонажей
    for pid in player_ids:
        game.characters[pid] = create_weak_character()

    # Быстро переходим к Phase2
    eng = GameEngine(game, initializer, game_data)
    eng.execute(GameAction(type=ActionType.START_GAME))

    # Настраиваем команды
    bunker_players = player_ids[:2]
    outside_players = player_ids[2:]

    game.team_in_bunker = set(bunker_players)
    game.team_outside = set(outside_players)
    game.eliminated_ids = set(outside_players)

    # Инициализируем Phase2
    eng._init_phase2()

    return eng, game, game_data


def test_simple_successful_action():
    """Простой тест успешного действия"""
    print("\n=== TEST: Simple Successful Action ===")

    eng, game, game_data = setup_full_game_for_success()

    # Настраиваем высокий бросок для успеха
    fixed_rng = FixedRandomForTesting(roll_sequence=[20])  # максимальный бросок
    eng._phase2_engine.rng = fixed_rng

    # Переключаемся на команду бункера
    game.phase2_current_team = "bunker"
    eng._phase2_engine._team_states["bunker"].current_player_index = 0

    initial_hp = game.phase2_bunker_hp
    print(f"Initial bunker HP: {initial_hp}")

    # Добавляем одно действие от одного игрока
    current_player = eng._phase2_engine.get_current_player()
    assert current_player is not None

    eng._phase2_engine.add_player_action(current_player, "repair_bunker")

    # Завершаем ход команды
    while not eng._phase2_engine.is_team_turn_complete():
        next_player = eng._phase2_engine.get_current_player()
        if next_player:
            eng._phase2_engine.add_player_action(next_player, "repair_bunker")

    # Обрабатываем действие
    result = eng._phase2_engine.process_current_action()

    print(
        f"Action result: success={result.success}, roll={result.roll_result}, stats={result.combined_stats}, difficulty={result.difficulty}"
    )
    print(f"Total: {result.roll_result + result.combined_stats} vs {result.difficulty}")

    # Проверяем результат
    assert result.success is True
    assert result.crisis_triggered is None
    assert game.phase2_bunker_hp > initial_hp

    print(
        f"✓ Action succeeded, HP increased from {initial_hp} to {game.phase2_bunker_hp}"
    )


def test_simple_failed_action_with_minigame():
    """Простой тест провалившегося действия с мини-игрой"""
    print("\n=== TEST: Simple Failed Action with Minigame ===")

    eng, game, game_data = setup_full_game_for_failure()

    # Проверяем сложность действий
    action_def = game_data.phase2_actions["repair_bunker"]
    print(f"Action difficulty: {action_def.difficulty}")
    print(f"Action mini_games: {action_def.mini_games}")

    # Настраиваем низкий бросок для провала
    fixed_rng = FixedRandomForTesting(
        roll_sequence=[1],  # низкий бросок
        choice_sequence=["building_challenge"],  # выбираем мини-игру
    )
    eng._phase2_engine.rng = fixed_rng

    # Переключаемся на команду бункера
    game.phase2_current_team = "bunker"
    eng._phase2_engine._team_states["bunker"].current_player_index = 0

    # Проверяем статы персонажей
    current_player = eng._phase2_engine.get_current_player()
    char_stats = game.characters[current_player].aggregate_stats()
    print(f"Character stats: {char_stats}")

    # Выполняем действие
    eng._phase2_engine.add_player_action(current_player, "repair_bunker")

    # Завершаем ход команды
    while not eng._phase2_engine.is_team_turn_complete():
        next_player = eng._phase2_engine.get_current_player()
        if next_player:
            eng._phase2_engine.add_player_action(next_player, "repair_bunker")

    # Обрабатываем действие
    result = eng._phase2_engine.process_current_action()

    print(
        f"Action result: success={result.success}, roll={result.roll_result}, stats={result.combined_stats}, difficulty={result.difficulty}"
    )
    print(f"Total: {result.roll_result + result.combined_stats} vs {result.difficulty}")
    print(f"Crisis triggered: {result.crisis_triggered}")

    # Проверяем что действие провалилось и запустилась мини-игра
    assert result.success is False
    assert result.crisis_triggered == "action_minigame_repair_bunker"

    crisis = eng._phase2_engine.get_current_crisis()
    assert crisis is not None
    assert crisis.mini_game is not None

    print(f"✓ Mini-game started: {crisis.mini_game.name}")


def test_failed_action_win_minigame():
    """Тест провала действия с победой в мини-игре"""
    print("\n=== TEST: Failed Action, Win Minigame ===")

    eng, game, game_data = setup_full_game_for_failure()

    # Настраиваем провал действия
    fixed_rng = FixedRandomForTesting(
        roll_sequence=[1],  # низкий бросок
        choice_sequence=["building_challenge"],  # выбираем мини-игру
    )
    eng._phase2_engine.rng = fixed_rng

    # Переключаемся на команду бункера
    game.phase2_current_team = "bunker"
    eng._phase2_engine._team_states["bunker"].current_player_index = 0

    initial_hp = game.phase2_bunker_hp
    initial_morale = game.phase2_morale
    initial_supplies = game.phase2_supplies

    # Выполняем действие
    current_player = eng._phase2_engine.get_current_player()
    eng._phase2_engine.add_player_action(current_player, "repair_bunker")

    # Завершаем ход команды
    while not eng._phase2_engine.is_team_turn_complete():
        next_player = eng._phase2_engine.get_current_player()
        if next_player:
            eng._phase2_engine.add_player_action(next_player, "repair_bunker")

    # Обрабатываем действие
    result = eng._phase2_engine.process_current_action()

    # Проверяем что действие провалилось и запустилась мини-игра
    assert result.success is False
    assert result.crisis_triggered == "action_minigame_repair_bunker"

    crisis = eng._phase2_engine.get_current_crisis()
    assert crisis is not None
    print(f"Mini-game started: {crisis.mini_game.name}")

    # Команда бункера выигрывает мини-игру
    eng._phase2_engine.resolve_crisis(CrisisResult.BUNKER_WIN)

    # Проверяем что никаких негативных эффектов нет
    assert game.phase2_bunker_hp == initial_hp
    assert game.phase2_morale == initial_morale
    assert game.phase2_supplies == initial_supplies
    assert eng._phase2_engine.get_current_crisis() is None

    print(f"✓ Bunker won minigame, no negative effects applied")


def test_failed_action_lose_minigame():
    """Тест провала действия с поражением в мини-игре"""
    print("\n=== TEST: Failed Action, Lose Minigame ===")

    eng, game, game_data = setup_full_game_for_failure()

    # Настраиваем провал действия и выбор кризиса
    fixed_rng = FixedRandomForTesting(
        roll_sequence=[1],  # низкий бросок
        choice_sequence=[
            "resource_gathering",
            "resource_shortage",
        ],  # мини-игра и кризис
    )
    eng._phase2_engine.rng = fixed_rng

    # Переключаемся на команду бункера
    game.phase2_current_team = "bunker"
    eng._phase2_engine._team_states["bunker"].current_player_index = 0

    initial_supplies = game.phase2_supplies

    # Выполняем действие поиска припасов
    current_player = eng._phase2_engine.get_current_player()
    eng._phase2_engine.add_player_action(current_player, "search_supplies")

    # Завершаем ход команды
    while not eng._phase2_engine.is_team_turn_complete():
        next_player = eng._phase2_engine.get_current_player()
        if next_player:
            eng._phase2_engine.add_player_action(next_player, "search_supplies")

    # Обрабатываем действие
    result = eng._phase2_engine.process_current_action()

    # Проверяем что запустилась мини-игра
    assert result.success is False
    assert result.crisis_triggered == "action_minigame_search_supplies"

    crisis = eng._phase2_engine.get_current_crisis()
    assert crisis is not None
    print(f"Mini-game started: {crisis.mini_game.name}")

    # Команда бункера проигрывает мини-игру
    eng._phase2_engine.resolve_crisis(CrisisResult.BUNKER_LOSE)

    # Проверяем что применились эффекты кризиса
    crisis_def = game_data.phase2_crises["resource_shortage"]
    expected_supplies_damage = crisis_def.penalty_on_fail.get("supplies_damage", 0)

    assert game.phase2_supplies == initial_supplies - expected_supplies_damage
    assert eng._phase2_engine.get_current_crisis() is None

    print(f"✓ Bunker lost minigame, crisis effects applied")
    print(f"  Supplies: {initial_supplies} -> {game.phase2_supplies}")


def test_outside_team_failure():
    """Тест провала команды снаружи (без мини-игры)"""
    print("\n=== TEST: Outside Team Failure ===")

    eng, game, game_data = setup_full_game_for_failure()

    # Настраиваем провал действия
    fixed_rng = FixedRandomForTesting(roll_sequence=[1])  # низкий бросок
    eng._phase2_engine.rng = fixed_rng

    # Команда снаружи уже текущая по умолчанию
    assert game.phase2_current_team == "outside"

    initial_hp = game.phase2_bunker_hp

    # Выполняем действие
    current_player = eng._phase2_engine.get_current_player()
    eng._phase2_engine.add_player_action(current_player, "attack_bunker")

    # Завершаем ход команды
    while not eng._phase2_engine.is_team_turn_complete():
        next_player = eng._phase2_engine.get_current_player()
        if next_player:
            eng._phase2_engine.add_player_action(next_player, "attack_bunker")

    # Обрабатываем действие
    result = eng._phase2_engine.process_current_action()

    print(f"Outside action result: success={result.success}, roll={result.roll_result}")

    # Проверяем что действие провалилось, но эффекты провала применились сразу
    assert result.success is False
    assert result.crisis_triggered is None  # Нет мини-игры

    # У attack_bunker есть failure эффект
    action_def = game_data.phase2_actions["attack_bunker"]
    expected_damage = action_def.effects.get("failure", {}).get("bunker_damage", 0)
    if expected_damage > 0:
        assert game.phase2_bunker_hp == initial_hp - expected_damage
        print(f"✓ Failure damage applied: {initial_hp} -> {game.phase2_bunker_hp}")

    assert eng._phase2_engine.get_current_crisis() is None


if __name__ == "__main__":
    test_simple_successful_action()
    test_simple_failed_action_with_minigame()
    test_failed_action_win_minigame()
    test_failed_action_lose_minigame()
    test_outside_team_failure()
    print("\n🎉 ALL TESTS PASSED! 🎉")
