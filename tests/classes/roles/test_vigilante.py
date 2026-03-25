import pytest
from unittest.mock import AsyncMock, MagicMock
import discord
from classes.roles import VIGILANTE, Alignment

import tests.testutils as testutils


def test_vigilante_can_act_no_has_shot():
    player = testutils.new_test_player()
    assert VIGILANTE.can_act(player) is True


def test_vigilante_can_act_has_shot_false():
    player = testutils.new_test_player()
    player.role_state["has_shot"] = False
    assert VIGILANTE.can_act(player) is True


def test_vigilante_can_act_has_shot_true():
    player = testutils.new_test_player()
    player.role_state["has_shot"] = True
    assert VIGILANTE.can_act(player) is False


@pytest.mark.asyncio
async def test_vigilante_handle_selection():
    target = testutils.new_test_player()
    player = testutils.new_test_player()
    game = testutils.new_mock_game()

    await VIGILANTE.handle_selection(game, player, target)

    assert player.role_state["has_shot"] is True
    assert "kills" in game.night_actions
    assert target in game.night_actions["kills"]


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
async def test_vigilante_handle_button_click_already_shot():
    player = testutils.new_test_player(id=123)
    player.role_state["has_shot"] = True
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 123
    action_view = MagicMock()
    action_view.pending_humans = {123}
    game = testutils.new_mock_game()

    await VIGILANTE.handle_button_click(game, player, interaction, action_view)

    interaction.response.send_message.assert_called_once()
    assert 123 not in action_view.pending_humans
