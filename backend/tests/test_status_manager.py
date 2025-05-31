import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from bunker.core.loader import GameData
from bunker.domain.models.models import Game, Player, BunkerObjectState
from bunker.domain.models.character import Character
from bunker.domain.models.traits import Trait
from bunker.domain.phase2.status_manager import StatusManager

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def mock_game():
    """Создать мок игры для тестов"""
    host = Player("Host", "H")
    game = Game(host)

    # Добавляем игроков
    for i in range(4):
        player = Player(f"Player{i}", f"SID{i}")
        game.players[player.id] = player

    player_ids = list(game.players.keys())
    game.team_in_bunker = set(player_ids[:2])
    game.team_outside = set(player_ids[2:])

    # Добавляем персонажей
    for pid in player_ids:
        game.characters[pid] = Character(
            traits={
                "profession": Trait("Test Profession"),
                "phobia": Trait("Пирофобия"),
                "hobby": Trait("Test Hobby"),
                "health": Trait("Test Health"),
                "item": Trait("Test Item"),
                "personality": Trait("Test Personality"),
                "secret": Trait("Test Secret"),
            }
        )

    # Инициализируем Phase2 поля
    game.phase2_round = 1
    game.phase2_bunker_hp = 10
    game.phase2_morale = 10
    game.phase2_supplies = 10
    game.phase2_active_statuses = []
    game.phase2_active_statuses_detailed = {}
    game.phase2_bunker_objects = {
        "generator": BunkerObjectState("generator", "Генератор", "working"),
        "ventilation": BunkerObjectState("ventilation", "Вентиляция", "working"),
    }
    game.phase2_player_phobias = {}

    return game


@pytest.fixture
def mock_game_data():
    """Создать мок игровых данных"""
    game_data = Mock(spec=GameData)

    # Мокаем тестовые статусы
    from bunker.domain.models.status_models import StatusDef

    # Загружаем реальные статусы из тестового файла
    import yaml

    with open(DATA_DIR / "test_statuses.yml", "r", encoding="utf-8") as f:
        raw_statuses = yaml.safe_load(f)

    statuses = {}
    for raw_status in raw_statuses:
        status_def = StatusDef.from_raw(raw_status)
        statuses[status_def.id] = status_def

    game_data.statuses = statuses
    return game_data


@pytest.fixture
def status_manager(mock_game, mock_game_data):
    """Создать StatusManager для тестов"""
    return StatusManager(mock_game, mock_game_data)


class TestStatusManager:
    """Тесты для StatusManager"""

    def test_apply_status_success(self, status_manager, mock_game):
        """Тест успешного применения статуса"""
        result = status_manager.apply_status("test_fire", "test_source")

        assert result is True
        assert "test_fire" in mock_game.phase2_active_statuses
        assert "test_fire" in mock_game.phase2_active_statuses_detailed

        active_status = mock_game.phase2_active_statuses_detailed["test_fire"]
        assert active_status.status_id == "test_fire"
        assert active_status.source == "test_source"
        assert active_status.applied_at_round == 1
        assert active_status.remaining_rounds == -1  # until_removed

    def test_apply_status_no_stacking(self, status_manager, mock_game):
        """Тест что статусы не стакаются"""
        # Применяем статус первый раз
        result1 = status_manager.apply_status("test_fire", "source1")
        assert result1 is True

        # Пытаемся применить второй раз
        result2 = status_manager.apply_status("test_fire", "source2")
        assert result2 is False

        # Статус должен остаться один
        assert (
            len([s for s in mock_game.phase2_active_statuses if s == "test_fire"]) == 1
        )

    def test_apply_status_conflicts(self, status_manager, mock_game):
        """Тест конфликтующих статусов"""
        # Добавляем конфликтующий статус вручную
        mock_game.phase2_active_statuses.append("fire_extinguished")

        # Пытаемся применить test_fire который конфликтует с fire_extinguished
        result = status_manager.apply_status("test_fire", "test")

        assert result is False
        assert "test_fire" not in mock_game.phase2_active_statuses

    def test_remove_status(self, status_manager, mock_game):
        """Тест снятия статуса"""
        # Применяем статус
        status_manager.apply_status("test_fire", "test")
        assert status_manager.is_status_active("test_fire")

        # Снимаем статус
        result = status_manager.remove_status("test_fire")

        assert result is True
        assert not status_manager.is_status_active("test_fire")
        assert "test_fire" not in mock_game.phase2_active_statuses
        assert "test_fire" not in mock_game.phase2_active_statuses_detailed

    def test_remove_nonexistent_status(self, status_manager):
        """Тест снятия несуществующего статуса"""
        result = status_manager.remove_status("nonexistent")
        assert result is False

    def test_can_remove_status(self, status_manager, mock_game):
        """Тест проверки возможности снятия статуса"""
        status_manager.apply_status("test_fire", "test")

        # Правильное действие может снять
        assert status_manager.can_remove_status("test_fire", "extinguish_fire")

        # Неправильное действие не может
        assert not status_manager.can_remove_status("test_fire", "wrong_action")

        # Несуществующий статус нельзя снять
        assert not status_manager.can_remove_status("nonexistent", "extinguish_fire")

    def test_update_statuses_for_round(self, status_manager, mock_game):
        """Тест обновления статусов на новый раунд"""
        # Применяем статус на 3 раунда в раунде 1
        status_manager.apply_status("test_darkness", "test")

        # Переходим к раунду 2 - статус не истекает
        mock_game.phase2_round = 2
        expired = status_manager.update_statuses_for_round()
        assert len(expired) == 0
        assert status_manager.is_status_active("test_darkness")

        # Переходим к раунду 5 - статус истекает
        mock_game.phase2_round = 6
        expired = status_manager.update_statuses_for_round()
        assert "test_darkness" in expired
        assert not status_manager.is_status_active("test_darkness")

    def test_apply_per_round_effects(self, status_manager, mock_game):
        """Тест применения эффектов за раунд"""
        # Применяем статус с per_round_effects
        status_manager.apply_status("test_fire", "test")

        initial_hp = mock_game.phase2_bunker_hp
        initial_morale = mock_game.phase2_morale

        # Применяем эффекты
        effects = status_manager.apply_per_round_effects()

        # Проверяем что ресурсы изменились
        assert mock_game.phase2_bunker_hp == initial_hp - 1
        assert mock_game.phase2_morale == initial_morale - 1

        # Проверяем структуру возвращаемых эффектов
        assert "test_fire_bunker_hp" in effects
        assert "test_fire_morale" in effects

        hp_effect = effects["test_fire_bunker_hp"]
        assert hp_effect["old"] == initial_hp
        assert hp_effect["new"] == initial_hp - 1
        assert hp_effect["change"] == -1

    def test_get_action_modifiers(self, status_manager, mock_game):
        """Тест получения модификаторов действий"""
        # Применяем статус
        status_manager.apply_status("test_fire", "test")

        # Проверяем модификаторы для заблокированного действия
        blocked_mods = status_manager.get_action_modifiers("search_supplies")
        assert blocked_mods["blocked"] is True
        assert "test_fire" in blocked_mods["blocking_statuses"]

        # Проверяем модификаторы для затрудненного действия
        harder_mods = status_manager.get_action_modifiers("repair_bunker")
        assert harder_mods["difficulty_modifier"] == 3
        assert harder_mods["blocked"] is False

        # Проверяем модификаторы для незатронутого действия
        normal_mods = status_manager.get_action_modifiers("normal_action")
        assert normal_mods["difficulty_modifier"] == 0
        assert normal_mods["blocked"] is False

    def test_get_team_stat_modifiers(self, status_manager, mock_game):
        """Тест получения модификаторов статов команд"""
        # Применяем статус
        status_manager.apply_status("test_fire", "test")

        modifiers = status_manager.get_team_stat_modifiers()

        assert "bunker" in modifiers
        assert modifiers["bunker"]["ЗДР"] == -2
        assert modifiers["bunker"]["ТЕХ"] == -1

    def test_trigger_phobias(self, status_manager, mock_game):
        """Тест триггера фобий"""
        # Применяем статус который триггерит Пирофобию
        status_manager.apply_status("test_fire", "test")

        # Проверяем что фобия сработала у игроков с Пирофобией
        assert len(mock_game.phase2_player_phobias) > 0

        # Проверяем структуру фобии
        first_phobia = next(iter(mock_game.phase2_player_phobias.values()))
        assert first_phobia.phobia_name == "Пирофобия"
        assert first_phobia.trigger_source == "test_fire"

    def test_panic_attack_status(self, status_manager, mock_game):
        """Тест статуса панической атаки (make_useless)"""
        # Применяем статус паники
        status_manager.apply_status("test_panic", "test")

        # Проверяем что статус применился
        assert status_manager.is_status_active("test_panic")

        # Проверяем что статус временный (2 раунда)
        active_panic = mock_game.phase2_active_statuses_detailed["test_panic"]
        assert active_panic.remaining_rounds == 2

    def test_get_statuses_for_api(self, status_manager, mock_game):
        """Тест получения статусов для API"""
        # Применяем несколько статусов
        status_manager.apply_status("test_fire", "crisis_fire")
        status_manager.apply_status("test_darkness", "action_sabotage")

        api_statuses = status_manager.get_statuses_for_api()

        assert len(api_statuses) == 2

        # Проверяем структуру статуса в API
        fire_status = next(s for s in api_statuses if s["id"] == "test_fire")
        assert fire_status["name"] == "Тестовый пожар"
        assert fire_status["description"] == "Пожар для тестов"
        assert fire_status["severity"] == "high"
        assert fire_status["ui"]["icon"] == "fire"
        assert fire_status["ui"]["color"] == "error"
        assert len(fire_status["effects"]) > 0
        assert len(fire_status["removal_conditions"]) > 0
        assert fire_status["source"] == "crisis_fire"

        # Проверяем что эффекты читаемые
        effects = fire_status["effects"]
        assert any("bunker_hp каждый раунд" in effect for effect in effects)
        assert any("ЗДР для команды bunker" in effect for effect in effects)
        assert any("Блокирует действия" in effect for effect in effects)
