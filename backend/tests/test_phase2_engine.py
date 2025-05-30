from pathlib import Path
import pytest
import random

from bunker.core.loader import GameData
from bunker.domain.game_init import GameInitializer
from bunker.domain.models.models import Game, Player
from bunker.domain.phase2.phase2_engine import Phase2Engine
from bunker.domain.phase2.types import CrisisResult

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


@pytest.fixture(scope="module")
def game_data() -> GameData:
    return GameData(root=DATA_DIR)


@pytest.fixture(scope="module")
def initializer(game_data: GameData) -> GameInitializer:
    return GameInitializer(game_data)


def create_test_game(n_players: int = 8) -> Game:
    """Создать тестовую игру с игроками"""
    host = Player("Host", "HOST_SID")
    game = Game(host=host)

    for i in range(n_players):
        player = Player(f"Player{i}", f"SID_{i}")
        game.players[player.id] = player

    return game


def setup_phase2_teams(game):
    """Правильная настройка команд для тестов"""
    player_ids = list(game.players.keys())
    bunker_players = player_ids[: len(player_ids) // 2]
    outside_players = player_ids[len(player_ids) // 2 :]

    game.team_in_bunker = set(bunker_players)
    game.team_outside = set(outside_players)
    game.eliminated_ids = set(outside_players)

    # Создаем персонажей - ПОЛНАЯ ВЕРСИЯ
    from bunker.domain.models.traits import Trait

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
            return {"СИЛ": 3, "ТЕХ": 2, "ИНТ": 4, "ЗДР": 2, "ХАР": 3, "ЭМП": 2}

        def to_public_dict(self):
            return {
                attr: (self.traits[attr].name if attr in self.revealed else None)
                for attr in self.traits.keys()
            }

        def reveal(self, attr: str):
            if attr in self.traits and attr not in self.revealed:
                self.revealed.append(attr)

        def is_revealed(self, attr: str) -> bool:
            return attr in self.revealed

        @property
        def reveal_order(self):
            return list(self.traits.keys())

    for pid in player_ids:
        game.characters[pid] = MockCharacter()


def test_phase2_complete_flow(game_data: GameData, initializer: GameInitializer):
    """Тест полного флоу Phase2"""
    # Настройка игры
    game = create_test_game(8)
    initializer.setup_new_game(game)
    setup_phase2_teams(game)

    # Создание движка с фиксированным рандомом для предсказуемости
    rng = random.Random(42)
    engine = Phase2Engine(game, game_data, rng)

    # ═══════════════════════════════════════════════════════════════
    # ИНИЦИАЛИЗАЦИЯ
    # ═══════════════════════════════════════════════════════════════
    engine.initialize_phase2()

    # Проверяем базовую инициализацию
    assert game.phase2_bunker_hp == 7  # из конфига
    assert game.phase2_round == 1
    assert game.phase2_current_team == "outside"
    assert len(game.phase2_team_stats) == 2
    assert "bunker" in game.phase2_team_stats
    assert "outside" in game.phase2_team_stats

    # Проверяем что команды настроены
    assert len(game.team_in_bunker) == 4
    assert len(game.team_outside) == 4

    # ═══════════════════════════════════════════════════════════════
    # ХОД КОМАНДЫ СНАРУЖИ
    # ═══════════════════════════════════════════════════════════════
    print(
        f"\n=== РАУНД {game.phase2_round} - КОМАНДА {game.phase2_current_team.upper()} ==="
    )

    # Получаем доступные действия для команды снаружи
    available_actions = engine.get_available_actions("outside")
    assert len(available_actions) > 0

    action_ids = [action.id for action in available_actions]
    assert "attack_bunker" in action_ids

    # Получаем реальный порядок игроков от движка
    outside_team_state = engine._team_states["outside"]
    outside_players_order = outside_team_state.players

    # Проходим по всем игрокам команды снаружи в правильном порядке
    actions_chosen = []

    for i in range(len(outside_players_order)):
        current_player = engine.get_current_player()
        expected_player = outside_players_order[i]

        assert (
            current_player == expected_player
        ), f"Expected {expected_player}, got {current_player}"
        assert (
            current_player in game.team_outside
        ), f"Player {current_player} not in outside team"

        # Выбираем действие (первые два атакуют, остальные саботируют)
        action_id = "attack_bunker" if i < 2 else "sabotage"
        actions_chosen.append((current_player, action_id))

        success = engine.add_player_action(current_player, action_id)
        assert success, f"Failed to add action for {current_player}"

        print(f"Игрок {current_player} выбрал: {action_id}")

    # Проверяем что ход команды завершен
    assert engine.is_team_turn_complete()
    assert engine.can_process_actions()

    # Проверяем группировку действий
    assert len(game.phase2_action_queue) == 2  # attack_bunker и sabotage

    attack_group = next(
        (g for g in game.phase2_action_queue if g["action_type"] == "attack_bunker"),
        None,
    )
    sabotage_group = next(
        (g for g in game.phase2_action_queue if g["action_type"] == "sabotage"), None
    )

    assert attack_group is not None
    assert sabotage_group is not None
    assert len(attack_group["participants"]) == 2
    assert len(sabotage_group["participants"]) == 2

    print(
        f"Группировка: attack_bunker x{len(attack_group['participants'])}, sabotage x{len(sabotage_group['participants'])}"
    )

    # ═══════════════════════════════════════════════════════════════
    # ОБРАБОТКА ДЕЙСТВИЙ
    # ═══════════════════════════════════════════════════════════════
    action_results = []
    crisis_triggered = False

    while True:
        next_action = engine.get_next_action_to_process()
        if not next_action:
            break

        print(f"\nОбработка действия: {next_action['action_type']}")
        print(f"Участники: {next_action['participants']}")

        result = engine.process_current_action()
        action_results.append(result)

        print(
            f"Бросок: {result.roll_result}, Стат: {result.combined_stats}, Сложность: {result.difficulty}"
        )
        print(f"Результат: {'УСПЕХ' if result.success else 'НЕУДАЧА'}")
        print(f"Эффекты: {result.effects}")

        if result.crisis_triggered:
            crisis_triggered = True
            print(f"КРИЗИС АКТИВИРОВАН: {result.crisis_triggered}")
            break

    # Проверяем что обработались все действия или сработал кризис
    assert len(action_results) > 0

    # Проверяем влияние на HP бункера
    initial_hp = 7
    total_damage = sum(
        r.effects.get("bunker_damage", 0) for r in action_results if r.success
    )
    expected_hp = initial_hp - total_damage
    assert game.phase2_bunker_hp == max(0, expected_hp)

    print(f"HP бункера: {initial_hp} -> {game.phase2_bunker_hp} (урон: {total_damage})")

    # ═══════════════════════════════════════════════════════════════
    # ОБРАБОТКА КРИЗИСА (если есть)
    # ═══════════════════════════════════════════════════════════════
    if crisis_triggered:
        crisis = engine.get_current_crisis()
        assert crisis is not None

        print(f"\n=== КРИЗИС: {crisis.name} ===")
        print(f"Описание: {crisis.description}")
        print(f"Важные характеристики: {crisis.important_stats}")
        print(f"Преимущества команд: {crisis.team_advantages}")

        # Симулируем результат кризиса (команда бункера проигрывает)
        engine.resolve_crisis(CrisisResult.BUNKER_LOSE)

        print("Результат кризиса: Команда бункера ПРОИГРАЛА")
        print(f"HP бункера после кризиса: {game.phase2_bunker_hp}")

    # Завершаем ход команды
    engine.finish_team_turn()

    # Проверяем переключение команды
    assert game.phase2_current_team == "bunker"
    assert len(game.phase2_action_log) > 0

    # ═══════════════════════════════════════════════════════════════
    # ХОД КОМАНДЫ БУНКЕРА
    # ═══════════════════════════════════════════════════════════════
    print(
        f"\n=== РАУНД {game.phase2_round} - КОМАНДА {game.phase2_current_team.upper()} ==="
    )

    # Получаем доступные действия для команды бункера
    bunker_actions = engine.get_available_actions("bunker")
    assert len(bunker_actions) > 0

    bunker_action_ids = [action.id for action in bunker_actions]
    assert "repair_bunker" in bunker_action_ids

    # Получаем реальный порядок игроков команды бункера
    bunker_team_state = engine._team_states["bunker"]
    bunker_players_order = bunker_team_state.players

    # Команда бункера выбирает действия
    for i in range(len(bunker_players_order)):
        current_player = engine.get_current_player()
        expected_player = bunker_players_order[i]

        assert current_player == expected_player
        assert current_player in game.team_in_bunker

        # Все пытаются чинить бункер
        action_id = "repair_bunker"
        success = engine.add_player_action(current_player, action_id)
        assert success

        print(f"Игрок {current_player} выбрал: {action_id}")

    # Проверяем группировку - все выбрали одно действие
    assert len(game.phase2_action_queue) == 1
    repair_group = game.phase2_action_queue[0]
    assert repair_group["action_type"] == "repair_bunker"
    assert len(repair_group["participants"]) == 4

    print(f"Группировка: repair_bunker x{len(repair_group['participants'])}")

    # Обрабатываем действие команды бункера
    hp_before_repair = game.phase2_bunker_hp

    result = engine.process_current_action()
    print(f"\nОбработка действия: repair_bunker")
    print(
        f"Бросок: {result.roll_result}, Стат: {result.combined_stats}, Сложность: {result.difficulty}"
    )
    print(f"Результат: {'УСПЕХ' if result.success else 'НЕУДАЧА'}")

    if result.success:
        heal_amount = result.effects.get("bunker_heal", 0)
        print(f"Бункер восстановлен на {heal_amount} HP")
        assert game.phase2_bunker_hp == min(7, hp_before_repair + heal_amount)
    else:
        print("Ремонт не удался!")
        if result.crisis_triggered:
            print(f"КРИЗИС: {result.crisis_triggered}")

            # Обрабатываем кризис от неудачного ремонта
            crisis = engine.get_current_crisis()
            assert crisis is not None

            print(f"Кризис: {crisis.name}")
            # Симулируем что команда справилась с кризисом
            engine.resolve_crisis(CrisisResult.BUNKER_WIN)
            print("Команда бункера справилась с кризисом!")

    # Завершаем ход команды бункера
    engine.finish_team_turn()

    # Проверяем что мы перешли к следующему раунду
    assert game.phase2_current_team == "outside"
    assert game.phase2_round == 2

    print(f"\n=== ПЕРЕХОД К РАУНДУ {game.phase2_round} ===")

    # ═══════════════════════════════════════════════════════════════
    # ПРОВЕРКА УСЛОВИЙ ПОБЕДЫ
    # ═══════════════════════════════════════════════════════════════
    victory_condition = engine.check_victory_conditions()

    if victory_condition:
        print(f"\n=== ИГРА ЗАВЕРШЕНА ===")
        print(f"Условие победы: {victory_condition}")
        print(f"Победитель: {game.winner}")
        assert game.winner in ["bunker", "outside"]
    else:
        print(f"Игра продолжается. HP бункера: {game.phase2_bunker_hp}")
        assert game.winner is None

    # ═══════════════════════════════════════════════════════════════
    # ФИНАЛЬНЫЕ ПРОВЕРКИ
    # ═══════════════════════════════════════════════════════════════

    # Проверяем логирование
    assert len(game.phase2_action_log) >= 2  # минимум 2 хода команд

    # Проверяем что действия очищены для следующего хода
    assert len(game.phase2_action_queue) == 0
    assert len(game.phase2_processed_actions) == 0
    assert game.phase2_current_action_index == 0

    print(f"\n=== ТЕСТ ЗАВЕРШЕН УСПЕШНО ===")
    print(f"Обработано раундов: {game.phase2_round - 1}")
    print(f"Записей в логе: {len(game.phase2_action_log)}")
    print(f"Финальное состояние HP: {game.phase2_bunker_hp}")


def test_phase2_edge_cases(game_data: GameData):
    """Тест граничных случаев"""
    game = create_test_game(6)  # Меньше игроков
    setup_phase2_teams(game)

    # Установим неравные команды
    all_players = list(game.players.keys())
    game.team_in_bunker = set(all_players[:2])  # 2 в бункере
    game.team_outside = set(all_players[2:])  # 4 снаружи

    engine = Phase2Engine(game, game_data)
    engine.initialize_phase2()

    # Проверяем что команды неравные но работают
    assert len(game.team_in_bunker) == 2
    assert len(game.team_outside) == 4

    # Тестируем что нельзя добавить действие не в свой ход
    bunker_players = list(game.team_in_bunker)
    if bunker_players:
        wrong_player = bunker_players[0]  # игрок из бункера
        success = engine.add_player_action(wrong_player, "repair_bunker")
        assert not success  # должно провалиться т.к. ход команды снаружи

    # Тестируем несуществующее действие
    current_player = engine.get_current_player()
    if current_player:
        success = engine.add_player_action(current_player, "nonexistent_action")
        assert not success

    print("Тест граничных случаев пройден")


def test_phase2_victory_conditions(game_data: GameData):
    """Тест условий победы"""
    game = create_test_game(4)
    setup_phase2_teams(game)

    engine = Phase2Engine(game, game_data)
    engine.initialize_phase2()

    # Тест 1: Уничтожение бункера
    game.phase2_bunker_hp = 0
    victory = engine.check_victory_conditions()
    assert victory == "bunker_destroyed"
    assert game.winner == "outside"

    # Сброс
    game.phase2_bunker_hp = 5
    game.winner = None

    # Тест 2: Превышение лимита раундов
    max_rounds = game_data.phase2_config.game_settings.get("max_rounds", 10)
    game.phase2_round = max_rounds + 1
    victory = engine.check_victory_conditions()
    assert victory == "time_limit"
    assert game.winner == "bunker"

    print("Тест условий победы пройден")


if __name__ == "__main__":
    # Можно запустить напрямую для отладки
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))

    data = GameData(root=DATA_DIR)
    init = GameInitializer(data)

    print("Запуск комплексного теста Phase2...")
    test_phase2_complete_flow(data, init)
    test_phase2_edge_cases(data)
    test_phase2_victory_conditions(data)
    print("Все тесты пройдены!")
