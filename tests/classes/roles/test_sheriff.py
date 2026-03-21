import pytest
from unittest.mock import MagicMock, AsyncMock
from classes.roles import SHERIFF, Alignment


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


def test_sheriff_emoji():
    assert SHERIFF.emoji == "🤠"


def test_sheriff_alignment():
    assert SHERIFF.alignment == Alignment.TOWN


def test_sheriff_is_special():
    assert SHERIFF.is_special() is True


def test_sheriff_night_action_type():
    assert SHERIFF.night_action_type() == "investigate"


def test_sheriff_get_options_excludes_self(mock_game, mock_player):
    p1 = MagicMock()
    p1.alive = True
    p2 = MagicMock()
    p2.alive = True
    
    mock_game.get_alive_players.return_value = [mock_player, p1, p2]
    
    options = SHERIFF.get_options(mock_game, mock_player)
    
    assert len(options) == 2
    assert mock_player not in options
    assert p1 in options
    assert p2 in options


def test_sheriff_name():
    assert SHERIFF.name == "Sheriff"


@pytest.mark.asyncio
async def test_sheriff_on_selected_marks_player_acted_and_clears_pending(mock_game, mock_player):
    suspect = MagicMock()
    suspect.name = "Alice"
    suspect.role = MagicMock(alignment=Alignment.MAFIA)
    interaction = MagicMock()
    interaction.data = {"values": ["0"]}
    interaction.user.id = 123
    interaction.response.edit_message = AsyncMock()
    action_view = MagicMock()
    action_view.acted_players = set()
    action_view.pending_humans = {123}

    await SHERIFF.on_selected(mock_game, mock_player, interaction, [suspect], action_view)

    assert 123 in action_view.acted_players
    assert 123 not in action_view.pending_humans


@pytest.mark.asyncio
async def test_sheriff_on_selected_blocks_repeat_action_when_already_acted(mock_game, mock_player):
    suspect = MagicMock()
    suspect.name = "Alice"
    suspect.role = MagicMock(alignment=Alignment.MAFIA)
    interaction = MagicMock()
    interaction.data = {"values": ["0"]}
    interaction.user.id = 123
    interaction.response.edit_message = AsyncMock()
    action_view = MagicMock()
    action_view.acted_players = {123}
    action_view.pending_humans = {123}

    await SHERIFF.on_selected(mock_game, mock_player, interaction, [suspect], action_view)

    interaction.response.edit_message.assert_awaited_once_with(
        content="You have already performed your action!",
        view=None,
    )
    assert 123 in action_view.acted_players
    assert 123 in action_view.pending_humans
