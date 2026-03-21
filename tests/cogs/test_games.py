from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands

from cogs.games import GamesCog


def _make_cog(bot):
    bot.abstractors = []
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

        cog = GamesCog(mock_bot)
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

        cog = GamesCog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = owner

        player = MagicMock(spec=discord.User)
        player.id = 888
        player.mention = "<@888>"
        await cog.kick.callback(cog, mock_interaction, player)
        assert 888 not in abstractor.players


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
        owner.id = "222"
        abstractor = MagicMock()
        abstractor.channel = 123
        abstractor.running = True
        abstractor.owner = owner
        abstractor.game = MagicMock()
        abstractor.game.running = True
        mock_bot.abstractors = [abstractor]

        cog = GamesCog(mock_bot)
        mock_interaction.channel = MagicMock()
        mock_interaction.channel.id = 123
        mock_interaction.user = MagicMock(spec=discord.User)
        mock_interaction.user.id = 111

        await cog.stop.callback(cog, mock_interaction)
        assert abstractor.game.running is False
