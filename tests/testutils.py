from unittest.mock import AsyncMock, MagicMock
from copy import deepcopy

import discord
from discord.ext import commands

from classes.player import Player, AIAbstraction
from classes.roles import TOWN, Role

id_counter: int = 100


def new_test_player(
    name: str | None = None,
    *,
    id: int | None = None,
    role: Role | None = None,
    alive: bool = True,
    is_ai: bool = False,
) -> Player:
    global id_counter
    if is_ai:
        player = AIAbstraction("gpt-4o-mini", name or "AIPlayer").player
    else:
        user = MagicMock(spec=discord.Member)
        user.name = name or "TestPlayer"
        if id is not None:
            user.id = id
        else:
            user.id = id_counter
            id_counter += 1
        player = Player(user)
    if role is not None:
        player.role = role
    player.alive = alive
    return player


def make_player(
    name: str = "",
    role: Role = TOWN,
    *,
    alive: bool = True,
    is_ai: bool = False,
    id: int | None = None,
) -> Player:
    player = new_test_player(name or None, id=id, role=role, alive=alive, is_ai=is_ai)
    return player


def new_mock_member(user_id: int, name: str = "User") -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    return member


def new_mock_client() -> MagicMock:
    return MagicMock(spec=discord.Client)


def new_mock_bot() -> MagicMock:
    bot = MagicMock(spec=commands.Bot)
    bot.abstractors = []
    bot.user = MagicMock(spec=discord.User)
    bot.user.id = 999
    bot.get_channel = MagicMock(return_value=new_mock_text_channel())
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[])
    bot.add_cog = AsyncMock()
    return bot


def new_mock_text_channel() -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 123456
    channel.name = "test-channel"
    channel.send = AsyncMock()
    channel.fetch_message = AsyncMock()
    channel.set_permissions = AsyncMock()
    channel.create_thread = AsyncMock()
    channel.create_webhook = AsyncMock()
    channel.overwrites_for = MagicMock(
        return_value=MagicMock(is_empty=MagicMock(return_value=False))
    )
    return channel


def new_mock_thread() -> MagicMock:
    thread = MagicMock(spec=discord.Thread)
    thread.send = AsyncMock()
    thread.edit = AsyncMock()
    thread.add_user = AsyncMock()
    return thread


def new_mock_message() -> MagicMock:
    message = MagicMock(spec=discord.Message)
    message.id = 500
    message.content = "test message"
    message.delete = AsyncMock()
    message.edit = AsyncMock()
    return message


def new_mock_guild() -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 777
    guild.name = "TestGuild"
    guild.channels = []
    guild.roles = []
    guild.default_role = MagicMock()
    guild.me = MagicMock()
    guild.get_role = MagicMock(return_value=MagicMock())
    return guild


def new_mock_abstractor(*, owner_id: int = 1, owner_name: str = "Owner") -> MagicMock:
    owner = new_mock_member(owner_id, owner_name)
    owner_player = Player(owner)
    abstractor = MagicMock()
    abstractor.running = False
    abstractor.players = {owner_id: owner_player}
    abstractor.interactions = {}
    abstractor.bot = new_mock_client()
    abstractor.bot.get_channel = MagicMock()
    abstractor.owner = owner
    abstractor.last_lobby_id = None
    abstractor.save_config = MagicMock()
    abstractor.on_message = AsyncMock()
    abstractor.game = None
    return abstractor


def new_data_store(initial: dict | None = None) -> dict[str, object]:
    state = {"value": deepcopy(initial or {})}

    def load() -> dict:
        return deepcopy(state["value"])

    def save(data: dict) -> None:
        state["value"] = deepcopy(data)

    return {"state": state, "load": load, "save": save}


def new_mock_game(*, players: list[Player] | None = None) -> MagicMock:
    game = MagicMock()
    game.night_actions = {}
    game.turns = MagicMock()
    game.turns.create_ai_completion = AsyncMock()
    game.get_alive_players.return_value = players if players is not None else []
    return game


def new_mock_interaction(*, user_id: int | None = None) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = user_id if user_id is not None else 111
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


def new_mock_turn_manager() -> MagicMock:
    turns = MagicMock()
    turns.run_round = AsyncMock()
    turns.run_vote = AsyncMock()
    turns.broadcast = MagicMock()
    turns.set_channel = MagicMock()
    turns.set_participants = MagicMock()
    return turns
