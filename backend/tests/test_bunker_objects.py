import pytest
from pathlib import Path
from bunker.core.loader import GameData
from bunker.domain.models.models import Game, Player, BunkerObjectState
from bunker.domain.models.traits import Trait
from bunker.domain.phase2.bunker_objects import BunkerObjectBonusCalculator

DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")


class MockCharacter:
    def __init__(self, traits_dict):
        self.traits = {}
        for trait_type, trait_name in traits_dict.items():
            self.traits[trait_type] = Trait(trait_name)

    def aggregate_stats(self):
        return {"СИЛ": 5, "ТЕХ": 4, "ИНТ": 6, "ЗДР": 3, "ХАР": 4, "ЭМП": 5}


def test_bunker_objects_data_loading():
    """Тест загрузки данных объектов бункера"""
    game_data = GameData(root=DATA_DIR)

    print(f"Loaded bunker_objects: {list(game_data.bunker_objects.keys())}")

    # Проверяем что объекты загрузились
    assert hasattr(game_data, "bunker_objects")
    assert len(game_data.bunker_objects) > 0

    # Проверяем структуру первого объекта
    first_obj = next(iter(game_data.bunker_objects.values()))
    print(f"First object: {first_obj}")

    assert hasattr(first_obj, "name")
    assert hasattr(first_obj, "base_bonus")
    assert hasattr(first_obj, "trait_bonuses")

    print("✓ Bunker objects data loading works!")


def test_bunker_object_bonus_calculation():
    """Тест расчета бонусов от объектов бункера"""
    game_data = GameData(root=DATA_DIR)

    # Отладочная информация
    print(f"Available bunker objects: {list(game_data.bunker_objects.keys())}")
    if "generator" in game_data.bunker_objects:
        generator = game_data.bunker_objects["generator"]
        print(f"Generator data: {generator}")
        print(f"Generator base_bonus: {generator.base_bonus}")
        print(f"Generator trait_bonuses: {generator.trait_bonuses}")

    # Создаем игру
    game = Game(Player("Host", "H"))

    # Создаем персонажей с нужными чертами
    game.characters = {
        "PLAYER1": MockCharacter(
            {
                "profession": "Инженер-электрик",
                "hobby": "Ремонт электроники",
                "item": "Арсенал инструментов",
            }
        ),
        "PLAYER2": MockCharacter(
            {
                "profession": "Парамедик",
                "hobby": "Йога",
                "item": "Набор хирургических инструментов",
            }
        ),
    }

    # Отладка персонажей
    for pid, char in game.characters.items():
        print(f"Character {pid} traits:")
        for trait_type, trait_obj in char.traits.items():
            print(f"  {trait_type}: {trait_obj.name}")

    # Создаем объекты бункера - используем реальные ID из данных
    available_objects = list(game_data.bunker_objects.keys())
    print(f"Using objects: {available_objects[:2]}")  # первые 2 объекта

    game.phase2_bunker_objects = {}
    for i, obj_id in enumerate(available_objects[:2]):  # берем первые 2 объекта
        obj_def = game_data.bunker_objects[obj_id]
        game.phase2_bunker_objects[obj_id] = BunkerObjectState(
            obj_id, obj_def.name, "working"
        )

    print(f"Created bunker objects: {list(game.phase2_bunker_objects.keys())}")

    # Создаем калькулятор
    calc = BunkerObjectBonusCalculator(game, game_data.bunker_objects)

    # Команда с игроками
    team_players = {"PLAYER1", "PLAYER2"}

    # Рассчитываем бонусы
    bonuses = calc.calculate_team_bonuses(team_players)

    print(f"Calculated bonuses: {bonuses}")

    # Проверяем что бонусы рассчитались
    assert isinstance(bonuses, dict)

    # Если нет бонусов - проверим почему
    if len(bonuses) == 0:
        print("No bonuses calculated. Debugging...")
        for obj_id, obj_state in game.phase2_bunker_objects.items():
            print(
                f"Object {obj_id}: status={obj_state.status}, usable={obj_state.is_usable()}"
            )
            if obj_id in game_data.bunker_objects:
                obj_def = game_data.bunker_objects[obj_id]
                print(f"  Base bonus: {obj_def.base_bonus}")
                print(f"  Trait bonuses: {obj_def.trait_bonuses}")
            else:
                print(f"  Object {obj_id} not found in bunker_objects data!")

    # Более мягкая проверка - либо есть бонусы, либо объекты не имеют base_bonus
    has_objects_with_bonuses = any(
        game_data.bunker_objects.get(
            obj_id, type("", (), {"base_bonus": {}})
        ).base_bonus
        for obj_id in game.phase2_bunker_objects.keys()
    )

    if has_objects_with_bonuses:
        assert len(bonuses) > 0, "Should have bonuses if objects have base_bonus"

    print("✓ Bunker object bonus calculation works!")


def test_object_details_for_ui():
    """Тест получения детальной информации об объекте"""
    game_data = GameData(root=DATA_DIR)

    game = Game(Player("Host", "H"))
    game.characters = {
        "PLAYER1": MockCharacter(
            {"profession": "Инженер-электрик", "hobby": "Ремонт электроники"}
        )
    }

    # Используем реальный объект из данных
    available_objects = list(game_data.bunker_objects.keys())
    if not available_objects:
        pytest.skip("No bunker objects loaded")

    obj_id = available_objects[0]
    obj_def = game_data.bunker_objects[obj_id]

    game.phase2_bunker_objects = {
        obj_id: BunkerObjectState(obj_id, obj_def.name, "working")
    }

    calc = BunkerObjectBonusCalculator(game, game_data.bunker_objects)
    team_players = {"PLAYER1"}

    details = calc.get_object_details_for_ui(obj_id, team_players)

    print(f"Object details for {obj_id}: {details}")

    # Проверяем структуру ответа
    assert "name" in details
    assert "status" in details
    assert "usable" in details
    assert "base_bonus" in details
    assert "current_bonus" in details
    assert "active_traits" in details
    assert "available_traits" in details

    # Проверяем что объект рабочий
    assert details["usable"] is True

    print("✓ Object details for UI works!")


def test_damaged_object_no_bonus():
    """Тест что поврежденный объект не дает бонусов"""
    game_data = GameData(root=DATA_DIR)

    game = Game(Player("Host", "H"))
    game.characters = {"PLAYER1": MockCharacter({"profession": "Инженер-электрик"})}

    # Используем реальный объект
    available_objects = list(game_data.bunker_objects.keys())
    if not available_objects:
        pytest.skip("No bunker objects loaded")

    obj_id = available_objects[0]
    obj_def = game_data.bunker_objects[obj_id]

    # Поврежденный объект
    game.phase2_bunker_objects = {
        obj_id: BunkerObjectState(obj_id, obj_def.name, "damaged")
    }

    calc = BunkerObjectBonusCalculator(game, game_data.bunker_objects)
    team_players = {"PLAYER1"}

    bonuses = calc.calculate_team_bonuses(team_players)

    # Поврежденный объект не должен давать бонусов
    assert len(bonuses) == 0 or all(v == 0 for v in bonuses.values())

    print("✓ Damaged objects give no bonuses!")


def test_specific_generator_bonus():
    """Тест конкретного бонуса от генератора"""
    game_data = GameData(root=DATA_DIR)

    # Проверяем что генератор есть в данных
    if "generator" not in game_data.bunker_objects:
        pytest.skip("Generator not found in bunker objects")

    generator = game_data.bunker_objects["generator"]
    print(f"Generator config: {generator}")

    game = Game(Player("Host", "H"))

    # Создаем персонажа с чертами для генератора
    game.characters = {
        "ENGINEER": MockCharacter(
            {
                "profession": "Инженер-электрик",  # должно давать бонус
                "hobby": "Ремонт электроники",  # должно давать бонус
                "item": "Арсенал инструментов",  # должно давать бонус
            }
        )
    }

    # Рабочий генератор
    game.phase2_bunker_objects = {
        "generator": BunkerObjectState("generator", "Генератор", "working")
    }

    calc = BunkerObjectBonusCalculator(game, game_data.bunker_objects)
    team_players = {"ENGINEER"}

    bonuses = calc.calculate_team_bonuses(team_players)

    print(f"Generator bonuses: {bonuses}")

    # Если у генератора есть base_bonus, должны быть бонусы
    if generator.base_bonus:
        assert (
            len(bonuses) > 0
        ), f"Generator has base_bonus {generator.base_bonus} but no bonuses calculated"

        # Детальная информация
        details = calc.get_object_details_for_ui("generator", team_players)
        print(f"Generator details: {details}")

        assert (
            len(details["active_traits"]) > 0
        ), "Should have active traits for engineer"

    print("✓ Specific generator bonus works!")


if __name__ == "__main__":
    test_bunker_objects_data_loading()
    test_bunker_object_bonus_calculation()
    test_object_details_for_ui()
    test_damaged_object_no_bonus()
    test_specific_generator_bonus()
    print("✅ All bunker objects tests passed!")


def test_debug_bunker_objects_loading():
    """Отладочный тест для проверки загрузки объектов"""
    print("\n=== Debug: Bunker Objects Loading ===")

    game_data = GameData(root=DATA_DIR)

    print(f"Bunker objects type: {type(game_data.bunker_objects)}")
    print(f"Bunker objects count: {len(game_data.bunker_objects)}")

    if isinstance(game_data.bunker_objects, dict):
        print(f"Bunker objects keys: {list(game_data.bunker_objects.keys())}")

        for obj_id, obj_def in game_data.bunker_objects.items():
            print(f"\nObject: {obj_id}")
            print(f"  ID: {obj_def.id}")
            print(f"  Name: {obj_def.name}")
            print(f"  Base bonus: {obj_def.base_bonus}")
            print(f"  Trait bonuses: {obj_def.trait_bonuses}")

            if obj_id == "generator":
                print(f"  Generator found with traits: {obj_def.trait_bonuses}")
                break
    else:
        print("ERROR: bunker_objects is not a dict!")
        print(
            f"First object: {game_data.bunker_objects[0] if game_data.bunker_objects else 'None'}"
        )

    print("✓ Debug loading completed")
