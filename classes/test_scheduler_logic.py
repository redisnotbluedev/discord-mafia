"""Unit tests for role grouping logic in classes/scheduler.py."""

import pytest
from classes.roles import get_enabled_role_groups, DOCTOR, SHERIFF, VIGILANTE, JESTER, TOWN, MAFIA

def test_get_enabled_role_groups_basic():
    """Test that enabled roles are correctly grouped."""
    config = {
        "role_Doctor": True,
        "role_Sheriff": True,
        "role_Vigilante": False,
        "role_Jester": True,
        "mafia": 2,
        "town": 5,
    }
    
    neutral, special_town, special_mafia = get_enabled_role_groups(config)
    
    assert JESTER in neutral
    assert DOCTOR in special_town
    assert SHERIFF in special_town
    assert VIGILANTE not in special_town
    assert len(neutral) == 1
    assert len(special_town) == 2
    assert len(special_mafia) == 0

def test_get_enabled_role_groups_none_enabled():
    """Test that empty lists are returned when no special roles are enabled."""
    config = {
        "role_Doctor": False,
        "role_Sheriff": False,
        "mafia": 1,
        "town": 4,
    }
    
    neutral, special_town, _ = get_enabled_role_groups(config)
    
    assert len(neutral) == 0
    assert len(special_town) == 0

def test_get_enabled_role_groups_case_insensitivity():
    """Test that the grouping logic respects the case-insensitivity of get_role."""
    config = {
        "ROLE_DOCTOR": True,
        "jester": True,
    }
    
    neutral, special_town, _ = get_enabled_role_groups(config)
    
    assert JESTER in neutral
    assert DOCTOR in special_town

def test_get_enabled_role_groups_ignores_non_boolean_values():
    """Test that numeric or list values in config are ignored (they aren't roles)."""
    config = {
        "role_Doctor": True,
        "mafia": 3,
        "models": ["gpt-4o"],
    }
    
    neutral, special_town, _ = get_enabled_role_groups(config)
    
    assert DOCTOR in special_town
    assert len(special_town) == 1
    assert len(neutral) == 0
