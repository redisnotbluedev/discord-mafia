from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import discord
from discord.ext import commands

import tests.testutils as testutils

@pytest.fixture
def mock_bot():
    return testutils.new_mock_bot()


@pytest.fixture
def mock_channel():
    channel = testutils.new_mock_text_channel()
    channel.send = AsyncMock(return_value=MagicMock(spec=discord.Message, id=900))
    return channel


@pytest.fixture
def mock_user():
    user = testutils.new_mock_member(111, "TestUser")
    user.display_name = "TestUser"
    user.mention = "<@111>"
    user.bot = False
    return user


@pytest.fixture
def mock_guild():
    return testutils.new_mock_guild()


@pytest.fixture
def mock_message(mock_channel, mock_user):
    msg = testutils.new_mock_message()
    msg.author = mock_user
    msg.channel = mock_channel
    return msg


@pytest.fixture
def mock_interaction(mock_user, mock_channel):
    interaction = testutils.new_mock_interaction(user_id=mock_user.id)
    interaction.user = mock_user
    interaction.channel = mock_channel
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
def _patch_data(request):
    if request.node.get_closest_marker("no_patch_data"):
        yield
        return
    store = testutils.new_data_store()
    with patch("data.load", side_effect=store["load"]), \
         patch("data.save", side_effect=store["save"]), \
         patch("data.update_game_status"):
        yield


@pytest.fixture(autouse=True)
def _patch_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock):
        yield


@pytest.fixture(autouse=True)
def reset_id_counter():
    testutils.id_counter = 100
    yield
