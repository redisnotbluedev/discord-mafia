import pytest
from unittest.mock import MagicMock
from classes.roles import DOCTOR


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


def test_doctor_get_options_no_last_saved(mock_game, mock_player):
    p1 = MagicMock()
    p1.alive = True
    p2 = MagicMock()
    p2.alive = True
    p3 = MagicMock()
    p3.alive = True
    
    mock_game.get_alive_players.return_value = [p1, p2, p3]
    
    options = DOCTOR.get_options(mock_game, mock_player)
    
    assert len(options) == 3
    assert p1 in options
    assert p2 in options
    assert p3 in options


def test_doctor_get_options_with_last_saved(mock_game, mock_player):
    p1 = MagicMock()
    p1.alive = True
    p2 = MagicMock()
    p2.alive = True
    p3 = MagicMock()
    p3.alive = True
    
    mock_game.get_alive_players.return_value = [p1, p2, p3]
    mock_player.role_state["last_saved"] = p2
    
    options = DOCTOR.get_options(mock_game, mock_player)
    
    assert len(options) == 2
    assert p1 in options
    assert p3 in options
    assert p2 not in options


def test_doctor_get_options_can_save_self(mock_game, mock_player):
    p1 = MagicMock()
    p1.alive = True
    
    mock_game.get_alive_players.return_value = [mock_player, p1]
    
    options = DOCTOR.get_options(mock_game, mock_player)
    
    assert len(options) == 2
    assert mock_player in options
    assert p1 in options


@pytest.mark.asyncio
async def test_doctor_handle_selection(mock_game, mock_player):
    target = MagicMock()
    target.alive = True
    
    await DOCTOR.handle_selection(mock_game, mock_player, target)
    
    assert "saves" in mock_game.night_actions
    assert target in mock_game.night_actions["saves"]
    assert mock_player.role_state["pending_save"] == target


def test_doctor_alignment():
    from classes.roles import Alignment
    assert DOCTOR.alignment == Alignment.TOWN


def test_doctor_is_special():
    assert DOCTOR.is_special() is True


def test_doctor_night_action_type():
    assert DOCTOR.night_action_type() == "save"
