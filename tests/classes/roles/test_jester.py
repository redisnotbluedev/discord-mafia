import pytest
from unittest.mock import MagicMock
from classes.roles import JESTER, Alignment


@pytest.fixture
def mock_player():
    player = MagicMock()
    player.alive = True
    player.death_reason = None
    player.role_state = {}
    player.user = MagicMock()
    return player


def test_jester_win_condition_lynch(mock_player):
    mock_player.death_reason = "lynch"
    result = JESTER.win_condition(mock_player, [])
    assert result is True


def test_jester_win_condition_not_lynch(mock_player):
    mock_player.death_reason = "killed"
    result = JESTER.win_condition(mock_player, [])
    assert result is False


def test_jester_win_condition_none(mock_player):
    mock_player.death_reason = None
    result = JESTER.win_condition(mock_player, [])
    assert result is False


def test_jester_alignment():
    assert JESTER.alignment == Alignment.NEUTRAL


def test_jester_is_special():
    assert JESTER.is_special() is False


def test_jester_night_action_type():
    assert JESTER.night_action_type() is None


def test_jester_name():
    assert JESTER.name == "Jester"


def test_jester_emoji():
    assert JESTER.emoji == "🤡"
