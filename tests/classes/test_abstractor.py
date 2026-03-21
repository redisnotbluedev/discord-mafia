import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import discord

from classes.abstractor import GameAbstractor

CHANNEL_ID = 123456


def _http_response(status=404, reason="Not Found"):
    r = MagicMock()
    r.status = status
    r.reason = reason
    return r


@pytest.fixture
def abstractor(mock_bot):
    return GameAbstractor(channel=CHANNEL_ID, bot=mock_bot)


class TestInit:
    def test_defaults(self, mock_bot):
        a = GameAbstractor(channel=CHANNEL_ID, bot=mock_bot)
        assert a.channel == CHANNEL_ID
        assert a.channel_key == str(CHANNEL_ID)
        assert a.bot is mock_bot
        assert a.players == {}
        assert a.running is False
        assert a.owner is None
        assert a.interactions == {}
        assert a.game is None

    def test_loads_last_lobby_id(self, mock_bot):
        config = {"profiles": {str(CHANNEL_ID): {"last_lobby": 42}}}
        with patch("data.load", return_value=config):
            a = GameAbstractor(channel=CHANNEL_ID, bot=mock_bot)
        assert a.last_lobby_id == 42

    def test_last_lobby_id_defaults_none(self, mock_bot):
        a = GameAbstractor(channel=CHANNEL_ID, bot=mock_bot)
        assert a.last_lobby_id is None


class TestReset:
    def test_clears_all_state(self, abstractor, mock_user):
        abstractor.players[mock_user.id] = MagicMock()
        abstractor.owner = mock_user
        abstractor.interactions[mock_user.id] = MagicMock()
        abstractor.game = MagicMock()
        abstractor.reset()
        assert abstractor.players == {}
        assert abstractor.owner is None
        assert abstractor.interactions == {}
        assert abstractor.game is None


class TestOnMessage:
    async def test_false_is_no_op(self, abstractor):
        get_channel_mock = MagicMock()
        abstractor.bot.get_channel = get_channel_mock
        await abstractor.on_message(False)
        get_channel_mock.assert_not_called()

    async def test_true_triggers_lobby(self, abstractor, mock_channel):
        abstractor.bot.get_channel.return_value = mock_channel
        with patch("classes.views.StartGameView"):
            await abstractor.on_message(True)
        mock_channel.send.assert_called_once()

    async def test_running_routes_to_game(self, abstractor, mock_message):
        mock_turns = MagicMock()
        mock_turns.on_message = AsyncMock()
        mock_game = MagicMock()
        mock_game.turns = mock_turns
        mock_game.mafia_chat = None
        abstractor.game = mock_game
        abstractor.running = True
        mock_message.channel.id = CHANNEL_ID
        await abstractor.on_message(mock_message)
        mock_turns.on_message.assert_awaited_once_with(mock_message)

    async def test_not_running_posts_lobby(self, abstractor, mock_channel, mock_message):
        abstractor.running = False
        mock_message.channel.id = CHANNEL_ID
        abstractor.bot.get_channel.return_value = mock_channel
        with patch("classes.views.StartGameView"):
            await abstractor.on_message(mock_message)
        mock_channel.send.assert_called_once()

    async def test_race_condition_deletes_orphan(self, abstractor, mock_channel):
        sent_msg = MagicMock(spec=discord.Message)
        sent_msg.delete = AsyncMock()

        async def _send_and_set_running(*args, **kwargs):
            abstractor.running = True
            return sent_msg

        mock_channel.send = _send_and_set_running
        abstractor.bot.get_channel.return_value = mock_channel
        with patch("classes.views.StartGameView"):
            await abstractor.on_message(True)
        sent_msg.delete.assert_awaited_once()


class TestDeleteLastLobby:
    async def test_no_last_lobby_id_no_op(self, abstractor):
        abstractor.last_lobby_id = None
        abstractor.bot.get_channel = MagicMock()
        await abstractor._delete_last_lobby()
        abstractor.bot.get_channel.assert_not_called()

    async def test_deletes_message(self, abstractor, mock_channel):
        abstractor.last_lobby_id = 77
        mock_msg = MagicMock()
        mock_msg.delete = AsyncMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_msg)
        abstractor.bot.get_channel.return_value = mock_channel
        await abstractor._delete_last_lobby()
        mock_channel.fetch_message.assert_awaited_once_with(77)
        mock_msg.delete.assert_awaited_once()

    async def test_handles_not_found(self, abstractor, mock_channel):
        abstractor.last_lobby_id = 77
        mock_channel.fetch_message = AsyncMock(
            side_effect=discord.NotFound(_http_response(404, "Not Found"), "not found")
        )
        abstractor.bot.get_channel.return_value = mock_channel
        await abstractor._delete_last_lobby()

    async def test_handles_forbidden(self, abstractor, mock_channel):
        abstractor.last_lobby_id = 77
        mock_channel.fetch_message = AsyncMock(
            side_effect=discord.Forbidden(_http_response(403, "Forbidden"), "forbidden")
        )
        abstractor.bot.get_channel.return_value = mock_channel
        await abstractor._delete_last_lobby()

    async def test_handles_http_exception(self, abstractor, mock_channel):
        abstractor.last_lobby_id = 77
        mock_channel.fetch_message = AsyncMock(
            side_effect=discord.HTTPException(_http_response(500, "Internal Server Error"), "error")
        )
        abstractor.bot.get_channel.return_value = mock_channel
        await abstractor._delete_last_lobby()


class TestSaveConfig:
    def test_saves_last_lobby_id(self, abstractor):
        abstractor.last_lobby_id = 123
        with patch("data.load", return_value={}) as _mock_load, \
             patch("data.save") as mock_save:
            abstractor.save_config()
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["profiles"][str(CHANNEL_ID)]["last_lobby"] == 123
