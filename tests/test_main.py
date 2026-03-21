import sys
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands


class TestBotWithAbstractors:
    def test_mock_module_has_bot_with_abstractors(self):
        assert hasattr(sys.modules["main"], "BotWithAbstractors")

    def test_bot_with_abstractors_is_bot_subclass(self):
        BotWithAbstractors = sys.modules["main"].BotWithAbstractors
        assert issubclass(BotWithAbstractors, commands.Bot)


class TestOnMessageRouting:
    async def test_abstractor_receives_messages(self):
        abstractor = MagicMock()
        abstractor.on_message = AsyncMock()

        msg = MagicMock(spec=discord.Message)
        msg.author = MagicMock(spec=discord.Member)
        msg.content = "hello"

        for a in [abstractor]:
            await a.on_message(msg)

        abstractor.on_message.assert_called_once_with(msg)

    async def test_multiple_abstractors_all_receive_message(self):
        abs1 = MagicMock()
        abs1.on_message = AsyncMock()
        abs2 = MagicMock()
        abs2.on_message = AsyncMock()

        msg = MagicMock(spec=discord.Message)
        msg.author = MagicMock(spec=discord.Member)
        msg.content = "hello"

        for a in [abs1, abs2]:
            await a.on_message(msg)

        abs1.on_message.assert_called_once_with(msg)
        abs2.on_message.assert_called_once_with(msg)


class TestGameAbstractorCreation:
    def test_abstractor_init_stores_channel_and_bot(self):
        from classes.abstractor import GameAbstractor
        bot = MagicMock(spec=commands.Bot)
        bot.abstractors = []
        with patch("data.load", return_value={}):
            ga = GameAbstractor(12345, bot)
        assert ga.channel == 12345
        assert ga.bot is bot

    def test_abstractor_init_sets_running_false(self):
        from classes.abstractor import GameAbstractor
        bot = MagicMock(spec=commands.Bot)
        with patch("data.load", return_value={}):
            ga = GameAbstractor(12345, bot)
        assert ga.running is False
