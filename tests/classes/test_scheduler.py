import time
from unittest.mock import MagicMock, AsyncMock, patch
from typing import cast

import pytest
import discord

from classes.abstractor import GameAbstractor
from classes.player import Player, AIAbstraction
from classes.scheduler import MafiaSheduler, MafiaSchedulerConfig
from classes.roles import TOWN, MAFIA, DOCTOR, SHERIFF, JESTER
import tests.testutils as testutils


def _make_ai_stub(name, uid):
    ai = AIAbstraction(f"model-{uid}", name)
    return Player(ai)


def _make_abstractor(player_count):
    with patch("data.load", return_value={}):
        abstractor = GameAbstractor(channel=123456, bot=testutils.new_mock_bot())
    abstractor.players = {i: _make_ai_stub(f"Player{i}", i) for i in range(player_count)}
    abstractor.interactions = {}
    abstractor.running = False
    abstractor.reset = MagicMock()
    abstractor.on_message = AsyncMock()
    abstractor.game = None
    return abstractor


def _make_mock_game():
    game = MagicMock()
    game.players = []
    game.run = AsyncMock(return_value="Town")
    return game


def _make_scheduler(player_count=6):
    abstractor = _make_abstractor(player_count)
    lobby = MagicMock()
    lobby.generate_embed = MagicMock(return_value=MagicMock())
    message = testutils.new_mock_message()
    message.channel = testutils.new_mock_text_channel()
    message.channel.create_thread = AsyncMock(return_value=testutils.new_mock_thread())
    message.guild = testutils.new_mock_guild()
    with patch("classes.game.MafiaGame") as MockGame:
        mock_game = _make_mock_game()
        MockGame.return_value = mock_game
        scheduler = MafiaSheduler(abstractor, lobby, message)
    return scheduler


class TestMafiaSchedulerConfig:
    def test_config_has_required_keys(self):
        required = {"mafia", "town", "role_Doctor", "role_Sheriff", "role_Vigilante", "role_Jester"}
        assert required.issubset(set(MafiaSchedulerConfig.__annotations__.keys()))


class TestMafiaShedulerInit:
    def test_init_role_distribution_6_players(self):
        s = _make_scheduler(6)
        assert s.config["mafia"] == 2
        assert s.config["town"] == 4

    def test_init_role_distribution_5_players(self):
        s = _make_scheduler(5)
        assert s.config["mafia"] == 1
        assert s.config["town"] == 4

    def test_init_attempts_starts_at_zero(self):
        s = _make_scheduler()
        assert s.attempts == 0

    def test_init_sets_game_on_abstractor(self):
        abstractor = _make_abstractor(6)
        lobby = MagicMock()
        lobby.generate_embed = MagicMock(return_value=MagicMock())
        message = testutils.new_mock_message()
        message.channel = testutils.new_mock_text_channel()
        message.channel.create_thread = AsyncMock(return_value=testutils.new_mock_thread())
        message.guild = testutils.new_mock_guild()
        with patch("classes.game.MafiaGame") as MockGame:
            mock_game = _make_mock_game()
            MockGame.return_value = mock_game
            MafiaSheduler(abstractor, lobby, message)
        assert abstractor.game is mock_game

    def test_init_default_config_doctor_sheriff_enabled(self):
        s = _make_scheduler()
        assert s.config["role_Doctor"] is True
        assert s.config["role_Sheriff"] is True

    def test_init_default_config_vigilante_jester_disabled(self):
        s = _make_scheduler()
        assert s.config["role_Vigilante"] is False
        assert s.config["role_Jester"] is False


class TestSetupRoles:
    def _sched(self, player_count=5, **cfg):
        s = _make_scheduler(player_count)
        dict.update(s.config, cfg)
        return s

    def test_setup_roles_correct_total_assigned(self):
        s = self._sched(5, role_Doctor=False, role_Sheriff=False,
                        role_Vigilante=False, role_Jester=False)
        s.setup_roles()
        assert len(s.game.players) == 5

    def test_setup_roles_basic_town_mafia_distribution(self):
        s = self._sched(5, mafia=1, town=4,
                        role_Doctor=False, role_Sheriff=False,
                        role_Vigilante=False, role_Jester=False)
        s.setup_roles()
        roles = [p.role for p in s.game.players]
        assert roles.count(MAFIA) == 1
        assert roles.count(TOWN) == 4

    def test_setup_roles_doctor_assigned_when_enabled(self):
        s = self._sched(5, mafia=1, town=4,
                        role_Doctor=True, role_Sheriff=False,
                        role_Vigilante=False, role_Jester=False)
        s.setup_roles()
        roles = [p.role for p in s.game.players]
        assert DOCTOR in roles

    def test_setup_roles_neutral_jester_assigned_first(self):
        s = self._sched(6, mafia=1, town=5,
                        role_Doctor=False, role_Sheriff=False,
                        role_Vigilante=False, role_Jester=True)
        with patch("random.shuffle", lambda x: x):
            s.setup_roles()
        assert s.game.players[0].role == JESTER

    def test_setup_roles_calls_random_shuffle_once(self):
        s = _make_scheduler(5)
        with patch("random.shuffle") as mock_shuffle:
            s.setup_roles()
        mock_shuffle.assert_called_once()

    def test_setup_roles_adjusts_when_sum_exceeds_total(self):
        s = self._sched(5, mafia=4, town=4,
                        role_Doctor=False, role_Sheriff=False,
                        role_Vigilante=False, role_Jester=False)
        s.setup_roles()
        assert s.config["mafia"] + s.config["town"] == 5
        assert len(s.game.players) == 5

    def test_setup_roles_adjusts_when_sum_below_total(self):
        s = self._sched(6, mafia=1, town=2,
                        role_Doctor=False, role_Sheriff=False,
                        role_Vigilante=False, role_Jester=False)
        s.setup_roles()
        assert s.config["mafia"] + s.config["town"] == 6
        assert len(s.game.players) == 6


class TestStartGame:
    async def test_start_game_returns_false_below_5_players(self):
        s = _make_scheduler(4)
        result = await s.start_game()
        assert result is False

    async def test_start_game_returns_true_with_5_players(self):
        s = _make_scheduler(5)
        result = await s.start_game()
        assert result is True

    async def test_start_game_resets_abstractor_in_finally(self):
        s = _make_scheduler(5)
        await s.start_game()
        s.abstractor.reset.assert_called_once()

    async def test_start_game_sets_running_false_in_finally(self):
        s = _make_scheduler(5)
        s.abstractor.running = True
        await s.start_game()
        assert s.abstractor.running is False

    async def test_start_game_calls_set_permissions(self):
        s = _make_scheduler(5)
        channel = cast(MagicMock, s.message.channel)
        guild_data = {"guilds": {"777": {"player_role": 42}}}
        with patch("data.load", return_value=guild_data):
            await s.start_game()
        assert channel.set_permissions.called

    async def test_start_game_creates_mafia_thread(self):
        s = _make_scheduler(5)
        channel = cast(MagicMock, s.message.channel)
        guild_data = {"guilds": {"777": {"player_role": 42}}}
        with patch("data.load", return_value=guild_data):
            await s.start_game()
        channel.create_thread.assert_called_once_with(
            name="Mafia Private Chat", invitable=False
        )

    async def test_start_game_locks_mafia_thread_in_finally(self):
        s = _make_scheduler(5)
        channel = cast(MagicMock, s.message.channel)
        guild_data = {"guilds": {"777": {"player_role": 42}}}
        with patch("data.load", return_value=guild_data):
            await s.start_game()
        mock_thread = channel.create_thread.return_value
        mock_thread.edit.assert_called_once_with(locked=True)

    async def test_start_game_set_permissions_locks_everyone(self):
        s = _make_scheduler(5)
        channel = cast(MagicMock, s.message.channel)
        guild = cast(MagicMock, s.message.guild)
        guild_data = {"guilds": {"777": {"player_role": 42}}}
        with patch("data.load", return_value=guild_data):
            await s.start_game()
        calls = channel.set_permissions.call_args_list
        targets = [c.args[0] for c in calls]
        assert guild.default_role in targets


class TestSchedule:
    async def test_schedule_stores_task_reference(self):
        s = _make_scheduler(5)
        captured = {}
        created_task = MagicMock()

        def _capture_task(coro):
            captured["coro"] = coro
            return created_task

        with patch("asyncio.create_task", side_effect=_capture_task) as mock_create_task:
            s.schedule(time.time() + 100)
        mock_create_task.assert_called_once()
        assert s.start_job is created_task
        captured["coro"].close()
