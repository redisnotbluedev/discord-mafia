"""Unit tests for turnmanager.py using pytest parametrization."""

import pytest
from .turnmanager import extract_choice

# Constants for test data options to avoid repetition
FACTION_OPTIONS = ["Abstain", "Town", "Mafia"]
NAME_OPTIONS = ["John", "Johnette", "Johnette Napolitano"]
OVERLAP_OPTIONS = ["John", "Bob", "John Bob"]
BANANA_OPTIONS = ["Banana", "Nanana", "Nan", "Anan", "Ana"]

@pytest.mark.parametrize("input_text, options, expected", [
    # Straightforward faction cases
    ("Town", FACTION_OPTIONS, "Town"),
    ("I abstain", FACTION_OPTIONS, "Abstain"),
    ("I choose mafia", FACTION_OPTIONS, "Mafia"),

    # Substring matches
    ("Johnette Napolitano", NAME_OPTIONS, "Johnette Napolitano"),
    ("I am voting for Johnette", NAME_OPTIONS, "Johnette"),
    ("john owes me fifty bucks its him", NAME_OPTIONS, "John"),

    # Late overlap matches
    ("John Bob", OVERLAP_OPTIONS, "John Bob"),
    ("I am voting for John", OVERLAP_OPTIONS, "John"),
    ("john owes me fifty bucks its him", OVERLAP_OPTIONS, "John"),

    # Partial overlap cases
    ("Banana", BANANA_OPTIONS, "Banana"),
    ("Nanana", BANANA_OPTIONS, "Nanana"),
    ("Nan", BANANA_OPTIONS, "Nan"),
    ("Anan", BANANA_OPTIONS, "Anan"),
    ("Ana", BANANA_OPTIONS, "Ana"),
    ("Bananana", BANANA_OPTIONS, "Nanana"),
    ("Banananan", BANANA_OPTIONS, "Anan"),
    ("Banananabananbana", BANANA_OPTIONS, "Ana"),
    ("Banananabananbanan", BANANA_OPTIONS, "Anan"),
    ("Banananabananbanana", BANANA_OPTIONS, "Banana"),
])
def test_extract_choice_matches(input_text, options, expected):
    """
    Test extraction of valid choices from input strings.
    
    Verifies that the correct option is returned when it matches or is contained
    within the input text, handling overlaps and substrings correctly.
    """
    assert extract_choice(input_text, options) == expected

@pytest.mark.parametrize("input_text, options", [
    ("MY HEAD IS FULL OF BEES", FACTION_OPTIONS),
    ("An", BANANA_OPTIONS),
])
def test_extract_choice_no_match(input_text, options):
    """
    Test cases where no valid choice should be extracted.
    
    Verifies that extract_choice returns None when no configured options
    can be found in the provided input text.
    """
    assert extract_choice(input_text, options) is None
