import pytest
from unittest.mock import MagicMock
from classes.roles import TOWN, Alignment


@pytest.fixture
def mock_player():
    player = MagicMock()
    player.alive = True
    player.role_state = {}
    player.user = MagicMock()
    return player


def test_town_is_special():
    assert TOWN.is_special() is False


def test_town_alignment():
    assert TOWN.alignment == Alignment.TOWN


def test_town_emoji():
    assert TOWN.emoji == "🏡"


def test_town_night_action_type():
    assert TOWN.night_action_type() is None


def test_town_name():
    assert TOWN.name == "Town"


def test_town_can_act(mock_player):
    result = TOWN.can_act(mock_player)
    assert result is True


def test_town_has_no_special_action_button(mock_player):
    assert TOWN.is_special() is False
    assert TOWN.can_act(mock_player) is True
