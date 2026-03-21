import pytest
from unittest.mock import MagicMock
from classes.roles import MAFIA, Alignment


@pytest.fixture
def mock_game():
    game = MagicMock()
    game.night_actions = {}
    game.get_alive_players.return_value = []
    return game


@pytest.fixture
def mock_player():
    player = MagicMock()
    player.alive = True
    player.role_state = {}
    player.user = MagicMock()
    return player


def test_mafia_is_special():
    assert MAFIA.is_special() is False


def test_mafia_alignment():
    assert MAFIA.alignment == Alignment.MAFIA


def test_mafia_emoji():
    assert MAFIA.emoji == "🔪"


def test_mafia_night_action_type():
    assert MAFIA.night_action_type() == "kill"


def test_mafia_name():
    assert MAFIA.name == "Mafia"


@pytest.mark.asyncio
async def test_mafia_handle_selection(mock_game, mock_player):
    target = MagicMock()
    target.alive = True
    
    await MAFIA.handle_selection(mock_game, mock_player, target)
    
    assert "kills" in mock_game.night_actions
    assert target in mock_game.night_actions["kills"]
