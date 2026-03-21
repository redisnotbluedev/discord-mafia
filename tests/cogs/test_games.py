import importlib
import sys
import types
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands


def _make_cog(bot):
    mock_main = types.ModuleType("main")

    class _MockBot(commands.Bot):
        def __init__(self, *args, **kwargs):
            pass

    mock_main.BotWithAbstractors = _MockBot
    sys.modules["main"] = mock_main
    sys.modules.pop("cogs.games", None)
    GamesCog = importlib.import_module("cogs.games").GamesCog
    return GamesCog(bot)


class TestGamesCogInit:
    def test_stores_bot(self, mock_bot):
        cog = _make_cog(mock_bot)
        assert cog.bot is mock_bot


class TestKickCommand:
    async def test_cannot_kick_self(self, mock_bot, mock_interaction):
        cog = _make_cog(mock_bot)
        mock_interaction.user = MagicMock(spec=discord.User)
        await cog.kick.callback(cog, mock_interaction, mock_interaction.user)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "yourself" in msg.lower()

    async def test_no_game_in_channel(self, mock_bot, mock_interaction):
        cog = _make_cog(mock_bot)
        player = MagicMock(spec=discord.User)
        player.id = 999
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        await cog.kick.callback(cog, mock_interaction, player)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "no ongoing game" in msg.lower()

    async def test_not_owner_cannot_kick(self, mock_bot, mock_interaction):
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.owner = MagicMock(spec=discord.User)
        mock_bot.abstractors = [abstractor]

        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = MagicMock(spec=discord.User)

        player = MagicMock(spec=discord.User)
        player.id = 888
        await cog.kick.callback(cog, mock_interaction, player)
        assert mock_interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_owner_kicks_player(self, mock_bot, mock_interaction):
        owner = MagicMock(spec=discord.User)
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.owner = owner
        abstractor.players = {888: MagicMock()}
        abstractor.game = MagicMock()
        abstractor.game.scheduler = None
        mock_bot.abstractors = [abstractor]

        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = owner

        player = MagicMock(spec=discord.User)
        player.id = 888
        player.mention = "<@888>"
        await cog.kick.callback(cog, mock_interaction, player)
        assert 888 not in abstractor.players


class TestLlama10Command:
    async def test_no_lobby_active(self, mock_bot, mock_interaction):
        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        await cog.llama10.callback(cog, mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "no lobby" in msg.lower()

    async def test_not_owner_rejected(self, mock_bot, mock_interaction):
        owner = MagicMock(spec=discord.User)
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.running = True
        abstractor.owner = owner
        mock_bot.abstractors = [abstractor]

        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = MagicMock(spec=discord.User)
        await cog.llama10.callback(cog, mock_interaction)
        assert mock_interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    @patch("builtins.open", side_effect=Exception("file not found"))
    async def test_handles_models_json_failure(self, mock_open, mock_bot, mock_interaction):
        owner = MagicMock(spec=discord.User)
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.running = True
        abstractor.owner = owner
        abstractor.players = {1: MagicMock()}
        mock_bot.abstractors = [abstractor]

        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = owner
        await cog.llama10.callback(cog, mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "Failed" in msg

    @patch("builtins.open", MagicMock(return_value=MagicMock(
        __enter__=MagicMock(return_value=MagicMock()),
        __exit__=MagicMock(return_value=False)
    )))
    @patch("json.load", return_value={"models": [{"model": "llama-4-maverick", "name": "Llama", "avatar": "llama.png"}], "avatar_template": "https://cdn.example.com/{}"})
    async def test_creates_10_llama_players(self, mock_json, mock_bot, mock_interaction):
        owner = MagicMock(spec=discord.User)
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.running = True
        abstractor.owner = owner
        abstractor.players = {}
        abstractor.game = MagicMock()
        abstractor.game.scheduler = None
        mock_bot.abstractors = [abstractor]

        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = owner
        await cog.llama10.callback(cog, mock_interaction)
        assert len(abstractor.players) == 10


class TestStopCommand:
    @patch.dict("os.environ", {"ADMIN_USERS": "111"})
    async def test_no_active_game(self, mock_bot, mock_interaction):
        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        await cog.stop.callback(cog, mock_interaction)
        assert "no lobby" in mock_interaction.response.send_message.call_args[0][0].lower()

    @patch.dict("os.environ", {"ADMIN_USERS": "111"})
    async def test_admin_can_stop_game(self, mock_bot, mock_interaction):
        owner = MagicMock(spec=discord.User)
        owner.id = 222
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.running = True
        abstractor.owner = owner
        abstractor.game = MagicMock()
        abstractor.game.running = True
        mock_bot.abstractors = [abstractor]

        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = MagicMock(spec=discord.User)
        mock_interaction.user.id = 111

        await cog.stop.callback(cog, mock_interaction)
        assert abstractor.game.running is False

    @patch.dict("os.environ", {"ADMIN_USERS": ""})
    async def test_owner_can_stop_own_game(self, mock_bot, mock_interaction):
        owner = MagicMock(spec=discord.User)
        owner.id = 222
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.running = True
        abstractor.owner = owner
        abstractor.game = MagicMock()
        abstractor.game.running = True
        mock_bot.abstractors = [abstractor]

        cog = _make_cog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = owner

        await cog.stop.callback(cog, mock_interaction)
        assert abstractor.game.running is False
