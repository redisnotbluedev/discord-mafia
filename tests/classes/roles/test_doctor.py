import pytest
from unittest.mock import AsyncMock, MagicMock
from classes.roles import DOCTOR, Alignment

import tests.testutils as testutils


def test_doctor_get_options_no_last_saved():
    p1 = testutils.new_test_player()
    p2 = testutils.new_test_player()
    p3 = testutils.new_test_player()
    player = testutils.new_test_player()

    game = testutils.new_mock_game(players=[p1, p2, p3])

    options = DOCTOR.get_options(game, player)

    assert len(options) == 3
    assert p1 in options
    assert p2 in options
    assert p3 in options


def test_doctor_get_options_with_last_saved():
    p1 = testutils.new_test_player()
    p2 = testutils.new_test_player()
    p3 = testutils.new_test_player()
    player = testutils.new_test_player()
    player.role_state["last_saved"] = p2

    game = testutils.new_mock_game(players=[p1, p2, p3])

    options = DOCTOR.get_options(game, player)

    assert len(options) == 2
    assert p1 in options
    assert p3 in options
    assert p2 not in options


def test_doctor_get_options_can_save_self():
    player = testutils.new_test_player()
    p1 = testutils.new_test_player()

    game = testutils.new_mock_game(players=[player, p1])

    options = DOCTOR.get_options(game, player)

    assert len(options) == 2
    assert player in options
    assert p1 in options


@pytest.mark.asyncio
async def test_doctor_handle_selection():
    target = testutils.new_test_player()
    player = testutils.new_test_player()
    game = testutils.new_mock_game()

    await DOCTOR.handle_selection(game, player, target)

    assert "saves" in game.night_actions
    assert target in game.night_actions["saves"]
    assert player.role_state["pending_save"] == target


def test_doctor_alignment():
    assert DOCTOR.alignment == Alignment.TOWN


def test_doctor_is_special():
    assert DOCTOR.is_special() is True


def test_doctor_night_action_type():
    assert DOCTOR.night_action_type() == "save"


def test_doctor_name():
    assert DOCTOR.name == "Doctor"


def test_doctor_emoji():
    assert DOCTOR.emoji == "🧑‍⚕️"


@pytest.mark.asyncio
async def test_doctor_blocks_repeat_action_when_called_twice():
    target = testutils.new_test_player("Alice")
    player = testutils.new_test_player(id=123)

    interaction_first = testutils.new_mock_interaction(user_id=123)
    interaction_first.data = {"values": ["0"]}
    interaction_second = testutils.new_mock_interaction(user_id=123)
    interaction_second.data = {"values": ["0"]}

    action_view = MagicMock()
    action_view.acted_players = set()
    action_view.pending_humans = {123}
    game = testutils.new_mock_game()

    await DOCTOR.on_selected(game, player, interaction_first, [target], action_view)
    await DOCTOR.on_selected(game, player, interaction_second, [target], action_view)

    assert "saves" in game.night_actions
    interaction_second.response.edit_message.assert_awaited_once_with(
        content="You have already performed your action!",
        view=None,
    )
    assert 123 in action_view.acted_players


@pytest.mark.asyncio
async def test_doctor_rejects_invalid_interaction_user():
    target = testutils.new_test_player("Alice")
    player = testutils.new_test_player(id=123)
    interaction = testutils.new_mock_interaction(user_id=999)
    interaction.data = {"values": ["0"]}
    action_view = MagicMock()
    action_view.acted_players = set()
    action_view.pending_humans = {123}
    game = testutils.new_mock_game()

    await DOCTOR.on_selected(game, player, interaction, [target], action_view)

    assert "saves" not in game.night_actions
    interaction.response.edit_message.assert_awaited_once_with(
        content="This action is no longer valid.",
        view=None,
    )
    assert action_view.acted_players == set()
    assert action_view.pending_humans == {123}


@pytest.mark.asyncio
async def test_doctor_rejects_missing_action_view():
    target = testutils.new_test_player("Alice")
    player = testutils.new_test_player(id=123)
    interaction = testutils.new_mock_interaction(user_id=123)
    interaction.data = {"values": ["0"]}
    game = testutils.new_mock_game()

    await DOCTOR.on_selected(game, player, interaction, [target], None)

    assert "saves" not in game.night_actions
    interaction.response.edit_message.assert_awaited_once_with(
        content="This action is no longer valid.",
        view=None,
    )
