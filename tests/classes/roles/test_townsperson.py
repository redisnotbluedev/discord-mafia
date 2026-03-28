import tests.testutils as testutils
from classes.roles import TOWN, Alignment


def test_town_is_special():
    assert TOWN.is_special() is False


def test_town_alignment():
    assert TOWN.alignment == Alignment.TOWN


def test_town_night_action_type():
    assert TOWN.night_action_type() is None
