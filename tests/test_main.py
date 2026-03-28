import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands


pytestmark = pytest.mark.no_patch_data


def load_main(config=None):
    sys.modules.pop("main", None)
    with (
        patch("dotenv.load_dotenv"),
        patch("data.load", return_value=config or {}),
        patch.object(commands.Bot, "run"),
    ):
        import main
        return importlib.reload(main)


class TestSetupHook:
    @pytest.mark.asyncio
    async def test_registers_cogs_and_syncs_commands(self):
        main = load_main()
        main.bot.add_cog = AsyncMock()
        main.bot.tree.sync = AsyncMock(return_value=[])

        await main.setup_hook()

        assert main.bot.add_cog.await_count == 3
        main.bot.tree.sync.assert_awaited_once()


class TestOnReady:
    @pytest.mark.asyncio
    async def test_on_ready_creates_abstractors_and_refreshes_lobbies(self):
        main = load_main({"profiles": {"123": {}, "456": {}}})
        main.bot.abstractors = []
        abstractor_a = MagicMock()
        abstractor_a.on_message = AsyncMock()
        abstractor_b = MagicMock()
        abstractor_b.on_message = AsyncMock()

        with patch.object(main, "GameAbstractor", side_effect=[abstractor_a, abstractor_b]) as mock_abs, \
             patch("data.update_game_status") as mock_update:
            await main.on_ready()

        assert mock_abs.call_count == 2
        abstractor_a.on_message.assert_awaited_once_with(True)
        abstractor_b.on_message.assert_awaited_once_with(True)
        assert main.bot.abstractors == [abstractor_a, abstractor_b]
        mock_update.assert_called_once_with(main.bot)


class TestOnMessage:
    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self):
        main = load_main()
        message = MagicMock(spec=discord.Message)
        message.author = main.bot.user
        message.content = "hello"
        main.bot.abstractors = [MagicMock(on_message=AsyncMock())]

        await main.on_message(message)

        main.bot.abstractors[0].on_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_routes_messages_to_all_abstractors(self):
        main = load_main()
        abstractor_a = MagicMock()
        abstractor_a.on_message = AsyncMock()
        abstractor_b = MagicMock()
        abstractor_b.on_message = AsyncMock()
        main.bot.abstractors = [abstractor_a, abstractor_b]

        message = MagicMock(spec=discord.Message)
        message.author = MagicMock(spec=discord.Member)
        message.author.id = 123
        message.content = "hello"

        await main.on_message(message)

        abstractor_a.on_message.assert_awaited_once_with(message)
        abstractor_b.on_message.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_eval_restricted_to_admin_id(self):
        main = load_main()
        main.bot.abstractors = []
        message = MagicMock(spec=discord.Message)
        message.author = MagicMock(spec=discord.Member)
        message.author.id = 1
        message.content = "!eval 1+1"
        message.channel = MagicMock()
        message.channel.send = AsyncMock()

        await main.on_message(message)

        message.channel.send.assert_not_called()
