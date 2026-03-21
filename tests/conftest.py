import sys
import types
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import discord
from discord.ext import commands

mock_main = types.ModuleType("main")

class _MockBot(commands.Bot):
    def __init__(self, *a, **kw):
        pass

_MockBot.abstractors = []
mock_main.BotWithAbstractors = _MockBot
mock_main.bot = MagicMock(spec=commands.Bot)
mock_main.bot.abstractors = []
mock_main.config = {}
sys.modules.setdefault("main", mock_main)


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=commands.Bot)
    bot.abstractors = []
    bot.user = MagicMock(spec=discord.User)
    bot.user.id = 999
    bot.get_channel = MagicMock(return_value=MagicMock(spec=discord.TextChannel))
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[])
    bot.add_cog = AsyncMock()
    return bot


@pytest.fixture
def mock_channel():
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 123456
    channel.name = "test-channel"
    channel.send = AsyncMock(return_value=MagicMock(spec=discord.Message, id=900))
    channel.fetch_message = AsyncMock()
    channel.set_permissions = AsyncMock()
    channel.create_thread = AsyncMock()
    channel.create_webhook = AsyncMock()
    return channel


@pytest.fixture
def mock_user():
    user = MagicMock(spec=discord.Member)
    user.id = 111
    user.name = "TestUser"
    user.display_name = "TestUser"
    user.mention = "<@111>"
    user.bot = False
    return user


@pytest.fixture
def mock_guild():
    guild = MagicMock(spec=discord.Guild)
    guild.id = 777
    guild.name = "TestGuild"
    guild.channels = []
    guild.roles = []
    return guild


@pytest.fixture
def mock_message(mock_channel, mock_user):
    msg = MagicMock(spec=discord.Message)
    msg.id = 500
    msg.content = "test message"
    msg.author = mock_user
    msg.channel = mock_channel
    msg.delete = AsyncMock()
    msg.edit = AsyncMock()
    return msg


@pytest.fixture
def mock_interaction(mock_user, mock_channel):
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = mock_user
    interaction.channel = mock_channel
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def mock_openai_client():
    client = AsyncMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "I vote for TestUser"
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[mock_choice])
    )
    return client


@pytest.fixture(autouse=True)
def _patch_data():
    with patch("data.load", return_value={}), \
         patch("data.save"), \
         patch("data.update_game_status"):
        yield


@pytest.fixture(autouse=True)
def _patch_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock):
        yield
