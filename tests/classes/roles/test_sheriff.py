import pytest
from unittest.mock import AsyncMock, MagicMock
from classes.roles import SHERIFF, Alignment

import tests.testutils as testutils


def test_sheriff_emoji():
    assert SHERIFF.emoji == "🤠"


def test_sheriff_alignment():
    assert SHERIFF.alignment == Alignment.TOWN


def test_sheriff_is_special():
    assert SHERIFF.is_special() is True


def test_sheriff_night_action_type():
    assert SHERIFF.night_action_type() == "investigate"


def test_sheriff_name():
    assert SHERIFF.name == "Sheriff"


def test_sheriff_get_options_excludes_self():
    player = testutils.new_test_player()
    p1 = testutils.new_test_player()
    p2 = testutils.new_test_player()

    game = testutils.new_mock_game(players=[player, p1, p2])

    options = SHERIFF.get_options(game, player)

    assert len(options) == 2
    assert player not in options
    assert p1 in options
    assert p2 in options


@pytest.mark.asyncio
async def test_sheriff_on_selected_marks_player_acted_and_clears_pending():
    suspect = testutils.new_test_player("Alice")
    suspect.role = MagicMock(alignment=Alignment.MAFIA)

    player = testutils.new_test_player(id=123)
    interaction = testutils.new_mock_interaction(user_id=123)
    interaction.data = {"values": ["0"]}
    action_view = MagicMock()
    action_view.acted_players = set()
    action_view.pending_humans = {123}
    game = testutils.new_mock_game()

    await SHERIFF.on_selected(game, player, interaction, [suspect], action_view)

    assert 123 in action_view.acted_players
    assert 123 not in action_view.pending_humans


@pytest.mark.asyncio
async def test_sheriff_on_selected_blocks_repeat_action_when_called_twice():
    suspect = testutils.new_test_player("Alice")
    suspect.role = MagicMock(alignment=Alignment.MAFIA)

    player = testutils.new_test_player(id=123)

    interaction_first = testutils.new_mock_interaction(user_id=123)
    interaction_first.data = {"values": ["0"]}
    interaction_second = testutils.new_mock_interaction(user_id=123)
    interaction_second.data = {"values": ["0"]}

    action_view = MagicMock()
    action_view.acted_players = set()
    action_view.pending_humans = {123}
    game = testutils.new_mock_game()

    await SHERIFF.on_selected(game, player, interaction_first, [suspect], action_view)
    await SHERIFF.on_selected(game, player, interaction_second, [suspect], action_view)

    interaction_second.response.edit_message.assert_awaited_once_with(
        content="You have already performed your action!",
        view=None,
    )
    assert 123 in action_view.acted_players


@pytest.mark.asyncio
async def test_sheriff_rejects_invalid_interaction_user():
    suspect = testutils.new_test_player("Alice")
    suspect.role = MagicMock(alignment=Alignment.MAFIA)

    player = testutils.new_test_player(id=123)
    interaction = testutils.new_mock_interaction(user_id=999)
    interaction.data = {"values": ["0"]}
    action_view = MagicMock()
    action_view.acted_players = set()
    action_view.pending_humans = {123}
    game = testutils.new_mock_game()

    await SHERIFF.on_selected(game, player, interaction, [suspect], action_view)

    interaction.response.edit_message.assert_awaited_once_with(
        content="This action is no longer valid.",
        view=None,
    )
    assert action_view.acted_players == set()
    assert action_view.pending_humans == {123}
