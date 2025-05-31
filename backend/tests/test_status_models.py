import pytest
from pathlib import Path
from bunker.domain.models.status_models import (
    StatusDef,
    StatusEffects,
    ActionModifier,
    ObjectEffect,
    PlayerEffect,
    RemovalCondition,
    StatusInteractions,
    StatusUI,
    ActiveStatus,
)


def test_action_modifier_from_raw():
    """Тест создания ActionModifier из raw данных"""
    raw_data = {
        "action_id": "repair_bunker",
        "difficulty_modifier": 3,
        "effectiveness": 0.8,
        "blocked": True,
    }

    modifier = ActionModifier.from_raw(raw_data)

    assert modifier.action_id == "repair_bunker"
    assert modifier.difficulty_modifier == 3
    assert modifier.effectiveness == 0.8
    assert modifier.blocked is True


def test_action_modifier_from_raw_minimal():
    """Тест создания ActionModifier с минимальными данными"""
    raw_data = {"action_id": "test_action"}

    modifier = ActionModifier.from_raw(raw_data)

    assert modifier.action_id == "test_action"
    assert modifier.difficulty_modifier == 0
    assert modifier.effectiveness == 1.0
    assert modifier.blocked is False


def test_object_effect_from_raw():
    """Тест создания ObjectEffect из raw данных"""
    raw_data = {
        "object_id": "generator",
        "status_change": "damaged",
        "effectiveness": 0.5,
    }

    effect = ObjectEffect.from_raw(raw_data)

    assert effect.object_id == "generator"
    assert effect.status_change == "damaged"
    assert effect.effectiveness == 0.5


def test_player_effect_from_raw():
    """Тест создания PlayerEffect из raw данных"""
    raw_data = {
        "type": "stat_penalties",
        "stats": {"ЗДР": -2, "ТЕХ": -1},
        "target_player": True,
    }

    effect = PlayerEffect.from_raw(raw_data)

    assert effect.type == "stat_penalties"
    assert effect.stats == {"ЗДР": -2, "ТЕХ": -1}
    assert effect.target_player is True


def test_status_effects_from_raw():
    """Тест создания StatusEffects из raw данных"""
    raw_data = {
        "per_round_effects": {"bunker_hp": -1, "morale": -1},
        "team_stats": {"bunker": {"ЗДР": -2}},
        "action_modifiers": [{"action_id": "repair_bunker", "difficulty_modifier": 3}],
        "bunker_objects": [{"object_id": "generator", "effectiveness": 0.5}],
        "triggers_phobias": ["Пирофобия"],
        "player_effects": [{"type": "stat_penalties", "stats": {"ЗДР": -1}}],
    }

    effects = StatusEffects.from_raw(raw_data)

    assert effects.per_round_effects == {"bunker_hp": -1, "morale": -1}
    assert effects.team_stats == {"bunker": {"ЗДР": -2}}
    assert len(effects.action_modifiers) == 1
    assert effects.action_modifiers[0].action_id == "repair_bunker"
    assert len(effects.bunker_objects) == 1
    assert effects.bunker_objects[0].object_id == "generator"
    assert effects.triggers_phobias == ["Пирофобия"]
    assert len(effects.player_effects) == 1


def test_status_def_from_raw():
    """Тест создания StatusDef из raw данных"""
    raw_data = {
        "id": "test_fire",
        "name": "Тестовый пожар",
        "description": "Пожар для тестов",
        "severity": "high",
        "duration_type": "until_removed",
        "effects": {"per_round_effects": {"bunker_hp": -1}},
        "removal_conditions": [{"action_id": "extinguish_fire"}],
        "interactions": {"enhanced_by": ["darkness"]},
        "ui": {"icon": "fire", "color": "error"},
    }

    status_def = StatusDef.from_raw(raw_data)

    assert status_def.id == "test_fire"
    assert status_def.name == "Тестовый пожар"
    assert status_def.severity == "high"
    assert status_def.duration_type == "until_removed"
    assert len(status_def.removal_conditions) == 1
    assert status_def.removal_conditions[0].action_id == "extinguish_fire"
    assert status_def.interactions.enhanced_by == ["darkness"]
    assert status_def.ui.icon == "fire"


def test_active_status_expiration():
    """Тест проверки истечения ActiveStatus"""
    # Статус на 3 раунда, применен в раунде 1
    active_status = ActiveStatus(
        status_id="test_status", applied_at_round=1, remaining_rounds=3, source="test"
    )

    # В раунде 2 не истек
    assert not active_status.is_expired(2)

    # В раунде 3 не истек
    assert not active_status.is_expired(3)

    # В раунде 4 истек (прошло 3 раунда: 2, 3, 4)
    assert not active_status.is_expired(4)

    # В раунде 5 тоже истек
    assert active_status.is_expired(5)


def test_active_status_until_removed():
    """Тест статуса до снятия"""
    active_status = ActiveStatus(
        status_id="permanent_status",
        applied_at_round=1,
        remaining_rounds=-1,  # до снятия
        source="test",
    )

    # Никогда не истекает
    assert not active_status.is_expired(10)
    assert not active_status.is_expired(100)


def test_active_status_to_dict():
    """Тест сериализации ActiveStatus"""
    active_status = ActiveStatus(
        status_id="test_status",
        applied_at_round=2,
        remaining_rounds=3,
        source="action_test",
        enhanced_by=["darkness"],
    )

    result = active_status.to_dict()

    expected = {
        "status_id": "test_status",
        "applied_at_round": 2,
        "remaining_rounds": 3,
        "source": "action_test",
        "enhanced_by": ["darkness"],
    }

    assert result == expected
