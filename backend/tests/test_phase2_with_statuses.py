import pytest
from pathlib import Path
from unittest.mock import Mock

from bunker.core.loader import GameData
from bunker.domain.engine import GameEngine
from bunker.domain.game_init import GameInitializer
from bunker.domain.types import GamePhase, ActionType, GameAction
from bunker.domain.models.models import Game, Player

# Используем основные данные
DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")
TEST_DATA_DIR = Path(__file__).parent / "data"


class TestGameData(GameData):
    """Расширенный GameData для тестов"""

    def __init__(self, root: Path | str):
        super().__init__(root)

        # Загружаем тестовые статусы если они есть
        test_statuses_file = TEST_DATA_DIR / "test_statuses.yml"
        if test_statuses_file.exists():
            import yaml
            from bunker.domain.models.status_models import StatusDef

            with open(test_statuses_file, encoding="utf8") as f:
                raw_statuses = yaml.safe_load(f)

            # Добавляем тестовые статусы к основным
            for raw in raw_statuses:
                status_def = StatusDef.from_raw(raw)
                self.statuses[status_def.id] = status_def


@pytest.fixture
def setup_phase2_with_statuses():
    """Подготовка игры для Phase2 с системой статусов"""
    # Используем TestGameData вместо обычной GameData
    game_data = TestGameData(root=DATA_DIR)
    initializer = GameInitializer(game_data)

    # Создаем игру с 4 игроками
    host = Player("Host", "H")
    game = Game(host)
    for i in range(4):
        p = Player(f"P{i}", f"S{i:}")
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


class TestPhase2WithStatuses:
    """Интеграционные тесты Phase2 с системой статусов"""

    def test_status_blocks_action(self, setup_phase2_with_statuses):
        """Тест что статус блокирует действие"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем статус пожара
        eng._phase2_engine._status_manager.apply_status("fire", "test")

        # Переключаемся на команду бункера
        game.phase2_current_team = "bunker"
        bunker_team = eng._phase2_engine._team_states["bunker"]
        bunker_team.current_player_index = 0

        # Проверяем модификаторы действий
        status_mods = eng._phase2_engine._status_manager.get_action_modifiers(
            "search_supplies"
        )
        assert status_mods["blocked"] is True
        assert "fire" in status_mods["blocking_statuses"]

    def test_status_modifies_action_difficulty(self, setup_phase2_with_statuses):
        """Тест что статус изменяет сложность действия"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем статус
        eng._phase2_engine._status_manager.apply_status("fire", "test")

        # Проверяем модификаторы
        status_mods = eng._phase2_engine._status_manager.get_action_modifiers(
            "repair_bunker"
        )
        assert status_mods["difficulty_modifier"] == 3

    def test_status_per_round_effects(self, setup_phase2_with_statuses):
        """Тест эффектов статуса за раунд"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем статус с per_round эффектами
        eng._phase2_engine._status_manager.apply_status("fire", "test")

        initial_hp = game.phase2_bunker_hp
        initial_morale = game.phase2_morale

        # Применяем эффекты за раунд
        effects = eng._phase2_engine._status_manager.apply_per_round_effects()

        # Проверяем что ресурсы уменьшились
        assert game.phase2_bunker_hp == initial_hp - 1
        assert game.phase2_morale == initial_morale - 1

    def test_status_removal_by_action(self, setup_phase2_with_statuses):
        """Тест снятия статуса действием"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем статус
        eng._phase2_engine._status_manager.apply_status("fire", "test")
        assert eng._phase2_engine._status_manager.is_status_active("fire")

        # Имитируем успешное выполнение действия extinguish_fire
        removed = eng._phase2_engine._check_status_removal("extinguish_fire")

        # Проверяем что статус снят
        assert "fire" in removed
        assert not eng._phase2_engine._status_manager.is_status_active("fire")

    def test_status_expiration(self, setup_phase2_with_statuses):
        """Тест истечения временного статуса"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем временный статус (2 раунда) в раунде 1
        assert game.phase2_round == 1
        eng._phase2_engine._status_manager.apply_status("high_morale", "test")
        assert eng._phase2_engine._status_manager.is_status_active("high_morale")

        # Раунд 2 - статус активен
        game.phase2_round = 2
        expired = eng._phase2_engine._status_manager.update_statuses_for_round()
        assert "high_morale" not in expired
        assert eng._phase2_engine._status_manager.is_status_active("high_morale")

        # Раунд 3 - статус активен
        game.phase2_round = 3
        expired = eng._phase2_engine._status_manager.update_statuses_for_round()
        assert "high_morale" not in expired
        assert eng._phase2_engine._status_manager.is_status_active("high_morale")

        # Раунд 4 - статус истекает
        game.phase2_round = 4
        expired = eng._phase2_engine._status_manager.update_statuses_for_round()
        assert "high_morale" in expired
        assert not eng._phase2_engine._status_manager.is_status_active("high_morale")

    def test_status_affects_team_stats(self, setup_phase2_with_statuses):
        """Тест влияния статуса на статы команд"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем статус
        eng._phase2_engine._status_manager.apply_status("fire", "test")

        # Получаем модификаторы статов
        modifiers = eng._phase2_engine._status_manager.get_team_stat_modifiers()

        # Проверяем что статы команды бункера изменились
        assert "bunker" in modifiers
        assert modifiers["bunker"]["ЗДР"] == -2
        assert modifiers["bunker"]["ТЕХ"] == -1

    def test_status_triggers_phobia(self, setup_phase2_with_statuses):
        """Тест триггера фобии от статуса"""
        eng, game, game_data = setup_phase2_with_statuses

        # Убеждаемся что у игрока есть подходящая фобия
        bunker_players = list(game.team_in_bunker)
        test_player = bunker_players[0]

        # Устанавливаем фобию вручную для теста
        from bunker.domain.models.traits import Trait

        game.characters[test_player].traits["phobia"] = Trait("Пирофобия")

        # Применяем статус который триггерит Пирофобию
        eng._phase2_engine._status_manager.apply_status("fire", "test")

        # Проверяем что фобия сработала
        assert test_player in game.phase2_player_phobias
        phobia_status = game.phase2_player_phobias[test_player]
        assert phobia_status.phobia_name == "Пирофобия"
        assert phobia_status.trigger_source == "fire"

    def test_status_in_api_response(self, setup_phase2_with_statuses):
        """Тест что статусы правильно отображаются в API"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем статус
        eng._phase2_engine._status_manager.apply_status("fire", "crisis_test")

        # Получаем API response
        view = eng.view()
        active_statuses = view["phase2"]["active_statuses"]

        assert len(active_statuses) == 1

        fire_status = active_statuses[0]
        assert fire_status["id"] == "fire"
        assert fire_status["name"] == "Пожар"
        assert (
            fire_status["description"]
            == "В бункере бушует пожар. Повреждает здания и блокирует действия."
        )
        assert fire_status["severity"] == "high"
        assert fire_status["source"] == "crisis_test"
        assert fire_status["ui"]["icon"] == "fire"
        assert fire_status["ui"]["color"] == "error"
        assert len(fire_status["effects"]) > 0
        assert len(fire_status["removal_conditions"]) > 0

    def test_multiple_statuses_interaction(self, setup_phase2_with_statuses):
        """Тест взаимодействия нескольких статусов"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем усиливающий статус
        eng._phase2_engine._status_manager.apply_status("darkness", "test")

        # Применяем усиливаемый статус
        eng._phase2_engine._status_manager.apply_status("fire", "test")

        # Проверяем что fire усилен darkness
        active_fire = game.phase2_active_statuses_detailed["fire"]
        assert "darkness" in active_fire.enhanced_by

        # Проверяем что оба статуса активны
        assert eng._phase2_engine._status_manager.is_status_active("fire")
        assert eng._phase2_engine._status_manager.is_status_active("darkness")

    def test_positive_status_application(self, setup_phase2_with_statuses):
        """Тест применения позитивного статуса"""
        eng, game, game_data = setup_phase2_with_statuses

        # Применяем позитивный статус
        eng._phase2_engine._status_manager.apply_status("high_morale", "action_success")

        # Проверяем что статус применился
        assert eng._phase2_engine._status_manager.is_status_active("high_morale")

        # Проверяем что статус временный
        active_positive = game.phase2_active_statuses_detailed["high_morale"]
        assert active_positive.remaining_rounds == 2
        assert active_positive.source == "action_success"

        # Получаем модификаторы статов
        modifiers = eng._phase2_engine._status_manager.get_team_stat_modifiers()

        # Проверяем что статы команды бункера улучшились
        assert "bunker" in modifiers
        assert modifiers["bunker"]["ХАР"] == 3
        assert modifiers["bunker"]["ЭМП"] == 2
