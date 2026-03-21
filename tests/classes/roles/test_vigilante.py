import pytest
from unittest.mock import MagicMock
from classes.roles import VIGILANTE, Alignment


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


def test_vigilante_can_act_no_has_shot(mock_player):
    result = VIGILANTE.can_act(mock_player)
    assert result is True


def test_vigilante_can_act_has_shot_false(mock_player):
    mock_player.role_state["has_shot"] = False
    result = VIGILANTE.can_act(mock_player)
    assert result is True


def test_vigilante_can_act_has_shot_true(mock_player):
    mock_player.role_state["has_shot"] = True
    result = VIGILANTE.can_act(mock_player)
    assert result is False


@pytest.mark.asyncio
async def test_vigilante_handle_selection(mock_game, mock_player):
    target = MagicMock()
    target.alive = True
    
    await VIGILANTE.handle_selection(mock_game, mock_player, target)
    
    assert mock_player.role_state["has_shot"] is True
    assert "kills" in mock_game.night_actions
    assert target in mock_game.night_actions["kills"]


def test_vigilante_skippable():
    assert VIGILANTE.skippable is True


def test_vigilante_alignment():
    assert VIGILANTE.alignment == Alignment.TOWN


def test_vigilante_is_special():
    assert VIGILANTE.is_special() is True


def test_vigilante_night_action_type():
    assert VIGILANTE.night_action_type() == "kill"


def test_vigilante_name():
    assert VIGILANTE.name == "Vigilante"


@pytest.mark.asyncio
async def test_vigilante_handle_button_click_already_shot(mock_game, mock_player):
    from unittest.mock import AsyncMock
    import discord
    mock_player.role_state["has_shot"] = True
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 123
    action_view = MagicMock()
    action_view.pending_humans = {123}
    
    await VIGILANTE.handle_button_click(mock_game, mock_player, interaction, action_view)
    
    interaction.response.send_message.assert_called_once()
    assert 123 not in action_view.pending_humans
