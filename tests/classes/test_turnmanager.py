import pytest
from classes.turnmanager import extract_choice

FACTION_OPTIONS = ["Abstain", "Town", "Mafia"]
NAME_OPTIONS = ["John", "Johnette", "Johnette Napolitano"]
OVERLAP_OPTIONS = ["John", "Bob", "John Bob"]
BANANA_OPTIONS = ["Banana", "Nanana", "Nan", "Anan", "Ana"]

@pytest.mark.parametrize("input_text, options, expected", [
    ("Town", FACTION_OPTIONS, "Town"),
    ("I abstain", FACTION_OPTIONS, "Abstain"),
    ("I choose mafia", FACTION_OPTIONS, "Mafia"),

    ("Johnette Napolitano", NAME_OPTIONS, "Johnette Napolitano"),
    ("I am voting for Johnette", NAME_OPTIONS, "Johnette"),
    ("john owes me fifty bucks its him", NAME_OPTIONS, "John"),

    ("John Bob", OVERLAP_OPTIONS, "John Bob"),
    ("I am voting for John", OVERLAP_OPTIONS, "John"),
    ("john owes me fifty bucks its him", OVERLAP_OPTIONS, "John"),

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
    assert extract_choice(input_text, options) == expected

@pytest.mark.parametrize("input_text, options", [
    ("MY HEAD IS FULL OF BEES", FACTION_OPTIONS),
    ("An", BANANA_OPTIONS),
])
def test_extract_choice_no_match(input_text, options):
    assert extract_choice(input_text, options) is None
