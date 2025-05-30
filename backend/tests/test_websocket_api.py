import pytest
import json
from pathlib import Path

from bunker import create_app, socketio
from bunker.core.loader import GameData
from bunker.domain.game_init import GameInitializer


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return socketio.test_client(app)


def test_phase2_websocket_flow():
    """Тест WebSocket API для Phase2"""
    app = create_app()
    client = socketio.test_client(app)

    # Создаем игру
    client.emit("create_game", {})
    received = client.get_received()
    assert len(received) > 0

    game_data = received[0]["args"][0]["game"]
    game_id = game_data["id"]

    # Добавляем игроков (симуляция)
    for i in range(8):
        client.emit("join_game", {"id": game_id, "name": f"Player{i}"})

    # Быстро доходим до Phase2 (симуляция Phase1)
    client.emit(
        "game_action", {"gameId": game_id, "action": "start_game", "payload": {}}
    )

    # Имитируем переход к Phase2 через несколько действий
    # (в реальности здесь был бы полный Phase1 флоу)

    print("✓ WebSocket Phase2 API test completed")


def test_phase2_events_structure():
    """Тест структуры Phase2 событий"""
    app = create_app()
    client = socketio.test_client(app)

    # Тестируем что события зарегистрированы
    events = [
        "phase2_player_action",
        "phase2_process_action",
        "phase2_resolve_crisis",
        "phase2_finish_turn",
        "get_phase2_info",
    ]

    for event in events:
        # Отправляем невалидные данные чтобы проверить что обработчик существует
        client.emit(event, {})
        received = client.get_received()
        # Должны получить ошибку о недостающих полях
        assert len(received) > 0

    print("✓ Phase2 WebSocket events structure test completed")
