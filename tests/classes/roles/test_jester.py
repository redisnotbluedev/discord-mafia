import pytest
from unittest.mock import MagicMock
from classes.roles import JESTER, Alignment

import tests.testutils as testutils


def test_jester_win_condition_lynch():
    player = testutils.new_test_player()
    player.death_reason = "lynch"
    assert JESTER.win_condition(player, [])


def test_jester_win_condition_not_lynch():
    player = testutils.new_test_player()
    player.death_reason = "mafia"
    assert not JESTER.win_condition(player, [])


def test_jester_win_condition_none():
    player = testutils.new_test_player()
    player.death_reason = None
    assert not JESTER.win_condition(player, [])


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
