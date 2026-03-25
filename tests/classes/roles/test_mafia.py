import pytest
from unittest.mock import MagicMock
from classes.roles import MAFIA, Alignment

import tests.testutils as testutils


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
async def test_mafia_handle_selection():
    target = testutils.new_test_player("Alice")
    player = testutils.new_test_player()
    game = testutils.new_mock_game()

    await MAFIA.handle_selection(game, player, target)

    assert "kills" in game.night_actions
    assert target in game.night_actions["kills"]
    assert target.alive is True
