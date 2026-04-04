"""Unit tests for the get_role function in classes/roles/__init__.py."""

import pytest
from classes.roles import (
    get_role, TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE, JESTER
)

@pytest.mark.parametrize("name, expected_role", [
    # Exact case
    ("Town", TOWN),
    ("Mafia", MAFIA),
    ("Doctor", DOCTOR),
    ("Sheriff", SHERIFF),
    ("Vigilante", VIGILANTE),
    ("Jester", JESTER),
    
    # Case-insensitive
    ("town", TOWN),
    ("MAFIA", MAFIA),
    ("dOcToR", DOCTOR),
    
    # Prefix 'role_'
    ("role_Town", TOWN),
    ("role_Mafia", MAFIA),
    ("role_Doctor", DOCTOR),
    ("role_Sheriff", SHERIFF),
    ("role_Vigilante", VIGILANTE),
    ("role_Jester", JESTER),
    
    # Prefix 'role_' case-insensitive
    ("ROLE_TOWN", TOWN),
    ("role_doctor", DOCTOR),
])
def test_get_role_valid_names(name, expected_role):
    """Test that get_role returns the correct singleton for valid names and prefixes."""
    role = get_role(name)
    assert role is expected_role
    assert role is not None

@pytest.mark.parametrize("invalid_name", [
    "NonExistent",
    "role_NonExistent",
    "",
    "role_",
    "Townie",
    "Mafioso",
])
def test_get_role_invalid_names(invalid_name):
    """Test that get_role returns None for invalid role names."""
    assert get_role(invalid_name) is None

def test_get_role_identity():
    """Explicitly verify that get_role returns the same object identity as the singletons."""
    assert get_role("Doctor") is DOCTOR
    assert get_role("role_Doctor") is DOCTOR
    assert get_role("Sheriff") is SHERIFF
    assert get_role("role_Sheriff") is SHERIFF
