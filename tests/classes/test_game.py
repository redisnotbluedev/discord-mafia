import random
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from classes.game import MafiaGame
from classes.player import AIAbstraction, Player
from classes.roles import Alignment, JESTER, MAFIA, TOWN, VIGILANTE
from classes.scheduler import MafiaSchedulerConfig

import tests.testutils as testutils


def make_game() -> MafiaGame:
    abstractor = testutils.new_mock_client()
    abstractor.bot = testutils.new_mock_client()
    scheduler = MagicMock()
    config: MafiaSchedulerConfig = {
        "mafia": 1,
        "town": 2,
        "role_Doctor": True,
        "role_Sheriff": True,
        "role_Vigilante": True,
        "role_Jester": True,
    }
    with patch("classes.game.AsyncOpenAI", return_value=MagicMock()):
        return MafiaGame(abstractor, scheduler, config)


def test_init_sets_expected_defaults():
    game = make_game()

    assert game.players == []
    assert game.day_number == 0
    assert game.night_actions == {}
    assert game.running is False
    assert game.turns is None
    assert game.channel is None
    assert game.mafia_chat is None


def test_get_alive_players_returns_only_alive_players():
    game = make_game()
    alive_one = testutils.make_player("AliveOne", TOWN, alive=True)
    dead_one = testutils.make_player("DeadOne", MAFIA, alive=False)
    alive_two = testutils.make_player("AliveTwo", TOWN, alive=True)
    game.players = [alive_one, dead_one, alive_two]

    assert game.get_alive_players() == [alive_one, alive_two]


def test_is_game_over_returns_no_one_when_not_running():
    game = make_game()
    game.running = False

    assert game.is_game_over() == "No one"


def test_is_game_over_returns_town_when_all_mafia_dead():
    game = make_game()
    game.running = True
    town_player = testutils.make_player("Townie", TOWN, alive=True)
    dead_mafia = testutils.make_player("Maf", MAFIA, alive=False)
    game.players = [town_player, dead_mafia]

    assert game.is_game_over() == "Town"


def test_is_game_over_returns_mafia_when_mafia_at_least_town():
    game = make_game()
    game.running = True
    mafia_player = testutils.make_player("Maf", MAFIA, alive=True)
    town_player = testutils.make_player("Townie", TOWN, alive=True)
    game.players = [mafia_player, town_player]

    assert game.is_game_over() == "Mafia"


def test_is_game_over_returns_false_while_game_continues():
    game = make_game()
    game.running = True
    mafia_player = testutils.make_player("Maf", MAFIA, alive=True)
    town_one = testutils.make_player("TownOne", TOWN, alive=True)
    town_two = testutils.make_player("TownTwo", TOWN, alive=True)
    game.players = [mafia_player, town_one, town_two]

    assert game.is_game_over() is False


def test_is_game_over_returns_individual_role_win_condition_first():
    game = make_game()
    game.running = True
    jester_player = testutils.make_player("Jester", JESTER, alive=False)
    jester_player.death_reason = "lynch"
    mafia_player = testutils.make_player("Maf", MAFIA, alive=True)
    town_player = testutils.make_player("Townie", TOWN, alive=True)
    game.players = [jester_player, mafia_player, town_player]

    assert game.is_game_over() == "Jester"


@pytest.mark.asyncio
async def test_run_creates_turn_manager_and_stops_when_winner_found():
    game = make_game()
    game.channel = testutils.new_mock_text_channel()
    game.players = [
        testutils.make_player("Maf", MAFIA, alive=True),
        testutils.make_player("Townie", TOWN, alive=True),
    ]

    turns = testutils.new_mock_turn_manager()
    game.run_night_phase = AsyncMock()
    game.run_day_phase = AsyncMock()
    game.is_game_over = MagicMock(side_effect=[False, False, False, "Town", "Town"])

    with patch("classes.game.TurnManager", return_value=turns) as tm_cls:
        winner = await game.run()

    tm_cls.assert_called_once_with(game.players, game.channel, game.bot, game.generator)
    game.run_night_phase.assert_awaited_once()
    game.run_day_phase.assert_awaited_once()
    turns.broadcast.assert_called_once_with("**GAME OVER!** Town wins!")
    assert winner == "Town"


@pytest.mark.asyncio
async def test_run_night_phase_resolves_vigilante_then_saved_mafia_target_and_clears_actions():
    game = make_game()
    game.day_number = 1
    game.channel = testutils.new_mock_text_channel()
    game.mafia_chat = testutils.new_mock_thread()
    game.mafia_chat.jump_url = "https://discord.com/channels/test"
    game.turns = testutils.new_mock_turn_manager()

    mafia_player = testutils.make_player("Maf", MAFIA, alive=True)
    vigilante = testutils.make_player("Vig", VIGILANTE, alive=True, is_ai=True)
    town_saved = testutils.make_player("SavedTown", TOWN, alive=True)
    town_victim = testutils.make_player("VigVictim", TOWN, alive=True)
    game.players = [mafia_player, vigilante, town_saved, town_victim]

    async def choose_target():
        game.night_actions["mafia_kill"] = town_saved
        game.night_actions["saves"] = [town_saved]
        game.night_actions["kills"] = [town_victim]

    game.mafia_choose_target = AsyncMock(side_effect=choose_target)

    actions_view = MagicMock()
    actions_view.wait_for_humans = AsyncMock()
    actions_view.handle_ai_special_action = AsyncMock()

    with (
        patch("classes.game.SpecialActionsView", return_value=actions_view),
        patch.object(TOWN, "on_night_end", new=AsyncMock()) as town_night_end,
        patch.object(MAFIA, "on_night_end", new=AsyncMock()) as mafia_night_end,
        patch.object(VIGILANTE, "on_night_end", new=AsyncMock()) as vigilante_night_end,
    ):
        await game.run_night_phase()

    assert town_victim.alive is False
    assert town_victim.death_reason == "vigilante"
    assert town_saved.alive is True
    game.mafia_choose_target.assert_awaited_once()
    actions_view.wait_for_humans.assert_awaited_once()
    actions_view.handle_ai_special_action.assert_awaited_once_with(vigilante)
    assert game.night_actions == {}
    assert game.channel.send.await_args_list[2].args[0].startswith("> VigVictim was killed by the Vigilante")
    assert game.channel.send.await_args_list[3].args[0] == "SavedTown was attacked by the Mafia but was saved!"
    assert town_night_end.await_count == 2
    mafia_night_end.assert_awaited_once_with(game, mafia_player)
    vigilante_night_end.assert_awaited_once_with(game, vigilante)


@pytest.mark.asyncio
async def test_run_day_phase_calls_discussion_then_voting_and_marks_victim_dead():
    game = make_game()
    game.channel = testutils.new_mock_text_channel()
    game.turns = testutils.new_mock_turn_manager()

    victim = testutils.make_player("VotedOut", TOWN, alive=True)
    game.players = [victim]
    game.discussion_phase = AsyncMock()
    game.voting_phase = AsyncMock(return_value=victim)

    await game.run_day_phase()

    game.discussion_phase.assert_awaited_once()
    game.voting_phase.assert_awaited_once()
    assert victim.alive is False
    game.channel.send.assert_awaited_once_with(
        "> VotedOut was eliminated! They were Town."
    )
    game.turns.broadcast.assert_called_once_with("VotedOut was eliminated! They were Town.")


@pytest.mark.asyncio
async def test_mafia_choose_target_broadcasts_mafia_context_and_targets_only_non_mafia_players():
    game = make_game()
    game.day_number = 2
    game.channel = testutils.new_mock_text_channel()
    game.mafia_chat = testutils.new_mock_thread()

    mafia_one = testutils.make_player("MafOne", MAFIA, alive=True)
    mafia_two = testutils.make_player("MafTwo", MAFIA, alive=True)
    town_one = testutils.make_player("TownOne", TOWN, alive=True)
    town_two = testutils.make_player("TownTwo", TOWN, alive=True)
    game.players = [mafia_one, mafia_two, town_one, town_two]

    turns = testutils.new_mock_turn_manager()
    turns.run_vote = AsyncMock(return_value=town_one)
    game.turns = turns

    await game.mafia_choose_target()

    turns.broadcast.assert_called_once_with(
        "You are part of the Mafia! Your team consists of: MafOne, MafTwo. Choose wisely who to eliminate."
    )
    turns.run_round.assert_awaited_once_with(rounds=2)
    turns.run_vote.assert_awaited_once()
    vote_kwargs = turns.run_vote.await_args.kwargs
    assert vote_kwargs["candidates"] == [town_one, town_two]
    assert vote_kwargs["break_ties_random"] is True
    assert game.night_actions["mafia_kill"] is town_one


@pytest.mark.asyncio
async def test_mafia_choose_target_falls_back_to_random_choice_when_vote_none():
    game = make_game()
    game.day_number = 3
    game.channel = testutils.new_mock_text_channel()
    game.mafia_chat = testutils.new_mock_thread()

    mafia_player = testutils.make_player("Maf", MAFIA, alive=True)
    town_one = testutils.make_player("TownOne", TOWN, alive=True)
    town_two = testutils.make_player("TownTwo", TOWN, alive=True)
    game.players = [mafia_player, town_one, town_two]

    turns = testutils.new_mock_turn_manager()
    turns.run_vote = AsyncMock(return_value=None)
    game.turns = turns

    with patch("random.choice", return_value=town_two) as random_choice:
        await game.mafia_choose_target()

    random_choice.assert_called_once_with([town_one, town_two])
    assert game.night_actions["mafia_kill"] is town_two


@pytest.mark.asyncio
async def test_run_night_phase_sends_nobody_killed_when_no_mafia_kill_and_no_vigilante_kills():
    game = make_game()
    game.day_number = 1
    game.channel = testutils.new_mock_text_channel()
    game.mafia_chat = testutils.new_mock_thread()
    game.mafia_chat.jump_url = "https://discord.com/channels/test"
    game.turns = testutils.new_mock_turn_manager()

    mafia_player = testutils.make_player("Maf", MAFIA, alive=True)
    town_player = testutils.make_player("Townie", TOWN, alive=True)
    game.players = [mafia_player, town_player]

    game.mafia_choose_target = AsyncMock(
        side_effect=lambda: game.night_actions.update({"mafia_kill": None})
    )
    actions_view = MagicMock()
    actions_view.wait_for_humans = AsyncMock()
    actions_view.handle_ai_special_action = AsyncMock()

    with (
        patch("classes.game.SpecialActionsView", return_value=actions_view),
        patch.object(TOWN, "on_night_end", new=AsyncMock()),
        patch.object(MAFIA, "on_night_end", new=AsyncMock()),
    ):
        await game.run_night_phase()

    assert game.channel.send.await_args_list[-1].args[0] == (
        "Nobody was killed last night. Either someone saved the target, or the Mafia didn't send a kill."
    )
