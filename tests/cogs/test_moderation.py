from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands

from cogs.moderation import ModerationCog


class TestModerationCogInit:
    def test_stores_bot(self, mock_bot):
        cog = ModerationCog(mock_bot)
        assert cog.bot is mock_bot


class TestSetupCommand:
    @patch.dict("os.environ", {"ADMIN_USERS": "222,333"})
    async def test_rejects_non_admin(self, mock_bot, mock_interaction):
        mock_interaction.user.id = 999
        cog = ModerationCog(mock_bot)
        await cog.setup.callback(cog, mock_interaction)
        assert mock_interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "not allowed" in msg.lower()

    @patch.dict("os.environ", {"ADMIN_USERS": "111"})
    async def test_checks_send_messages_permission(self, mock_bot, mock_interaction):
        mock_interaction.user.id = 111
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 123
        perms = MagicMock()
        perms.send_messages = False
        channel.permissions_for = MagicMock(return_value=perms)
        mock_interaction.channel = channel
        mock_interaction.guild = MagicMock(spec=discord.Guild)

        cog = ModerationCog(mock_bot)
        await cog.setup.callback(cog, mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "Send Messages" in msg

    @patch.dict("os.environ", {"ADMIN_USERS": "111"})
    async def test_rejects_already_setup_channel(self, mock_bot, mock_interaction):
        mock_interaction.user.id = 111
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 123
        perms = MagicMock()
        perms.send_messages = True
        perms.send_messages_in_threads = True
        perms.manage_roles = True
        perms.manage_webhooks = True
        perms.create_private_threads = True
        perms.manage_messages = True
        perms.manage_threads = True
        channel.permissions_for = MagicMock(return_value=perms)
        mock_interaction.channel = channel
        mock_interaction.guild = MagicMock(spec=discord.Guild)

        with patch("data.load", return_value={"profiles": {"123": {}}}):
            cog = ModerationCog(mock_bot)
            await cog.setup.callback(cog, mock_interaction)

        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "already set up" in msg.lower()

    @patch.dict("os.environ", {"ADMIN_USERS": "111"})
    async def test_successful_setup_creates_webhook(self, mock_bot, mock_interaction):
        mock_interaction.user.id = 111
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 456
        channel.set_permissions = AsyncMock()
        webhook = MagicMock(spec=discord.Webhook)
        webhook.url = "https://discord.com/api/webhooks/123/abc"
        channel.create_webhook = AsyncMock(return_value=webhook)
        perms = MagicMock()
        perms.send_messages = True
        perms.send_messages_in_threads = True
        perms.manage_roles = True
        perms.manage_webhooks = True
        perms.create_private_threads = True
        perms.manage_messages = True
        perms.manage_threads = True
        channel.permissions_for = MagicMock(return_value=perms)
        mock_interaction.channel = channel

        guild = MagicMock(spec=discord.Guild)
        guild.id = 789
        guild.me = MagicMock()
        guild.get_role = MagicMock(return_value=None)
        role = MagicMock(spec=discord.Role)
        role.id = 555
        guild.create_role = AsyncMock(return_value=role)
        mock_interaction.guild = guild

        mock_bot.abstractors = []

        with patch("data.load", return_value={}), \
             patch("data.save") as mock_save, \
             patch("data.update_game_status"):
            cog = ModerationCog(mock_bot)
            await cog.setup.callback(cog, mock_interaction)

        channel.create_webhook.assert_called_once()
        mock_save.assert_called_once()
        assert len(mock_bot.abstractors) == 1

    @patch.dict("os.environ", {"ADMIN_USERS": "111"})
    async def test_handles_exception_gracefully(self, mock_bot, mock_interaction):
        mock_interaction.user.id = 111
        mock_interaction.channel = None
        cog = ModerationCog(mock_bot)
        await cog.setup.callback(cog, mock_interaction)
        msg = mock_interaction.response.send_message.call_args[0][0]
        assert "Failed" in msg
