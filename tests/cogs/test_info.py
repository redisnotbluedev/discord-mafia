from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands

from cogs.info import InfoCog


class TestInfoCogInit:
    def test_stores_bot_reference(self, mock_bot):
        cog = InfoCog(mock_bot)
        assert cog.bot is mock_bot


class TestHelloCommand:
    async def test_hello_responds_with_pong(self, mock_bot, mock_interaction):
        mock_bot.latency = 0.042
        cog = InfoCog(mock_bot)
        await cog.hello.callback(cog, mock_interaction)
        mock_interaction.response.send_message.assert_called_once()
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "Pong" in msg
        assert "42.00ms" in msg

    async def test_hello_formats_latency(self, mock_bot, mock_interaction):
        mock_bot.latency = 0.1
        cog = InfoCog(mock_bot)
        await cog.hello.callback(cog, mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "100.00ms" in msg


class TestEchoCommand:
    @patch.dict("os.environ", {"ADMIN_USERS": "111,222"})
    async def test_echo_sends_to_channel_for_admin(self, mock_bot, mock_interaction):
        mock_interaction.user.id = 111
        target_channel = MagicMock(spec=discord.TextChannel)
        target_channel.send = AsyncMock()
        cog = InfoCog(mock_bot)
        await cog.echo.callback(cog, mock_interaction, "hello world", target_channel)
        target_channel.send.assert_called_once_with("hello world")
        mock_interaction.response.send_message.assert_called_once()

    @patch.dict("os.environ", {"ADMIN_USERS": "222,333"})
    async def test_echo_rejects_non_admin(self, mock_bot, mock_interaction):
        mock_interaction.user.id = 999
        target_channel = MagicMock(spec=discord.TextChannel)
        target_channel.send = AsyncMock()
        cog = InfoCog(mock_bot)
        await cog.echo.callback(cog, mock_interaction, "hello", target_channel)
        target_channel.send.assert_not_called()
        call_kwargs = mock_interaction.response.send_message.call_args
        assert call_kwargs.kwargs.get("ephemeral") is True


class TestInfoCommand:
    async def test_info_sends_embed(self, mock_bot, mock_interaction):
        cog = InfoCog(mock_bot)
        await cog.info.callback(cog, mock_interaction)
        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args
        embed = call_kwargs.kwargs.get("embed")
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Info"

    async def test_info_embed_has_system_field(self, mock_bot, mock_interaction):
        cog = InfoCog(mock_bot)
        await cog.info.callback(cog, mock_interaction)
        embed = mock_interaction.response.send_message.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "System" in field_names

    async def test_info_embed_has_credits_field(self, mock_bot, mock_interaction):
        cog = InfoCog(mock_bot)
        await cog.info.callback(cog, mock_interaction)
        embed = mock_interaction.response.send_message.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Credits" in field_names

    async def test_info_disallows_mentions(self, mock_bot, mock_interaction):
        cog = InfoCog(mock_bot)
        await cog.info.callback(cog, mock_interaction)
        call_kwargs = mock_interaction.response.send_message.call_args
        mentions = call_kwargs.kwargs.get("allowed_mentions")
        assert mentions is not None
        assert mentions.everyone is False
        assert mentions.roles is False
        assert mentions.users is False
