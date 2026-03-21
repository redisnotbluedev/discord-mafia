import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from classes.player import AIAbstraction, Player
from classes.roles import TOWN
from classes.turnmanager import TurnManager


def _human_player(user_id: int, name: str) -> Player:
    user = MagicMock(spec=discord.Member)
    user.id = user_id
    user.name = name
    player = Player(user)
    player.role = TOWN
    return player


def _ai_player(name: str = "AI One", model: str = "gpt-test") -> Player:
    ai_user = AIAbstraction(model=model, name=name)
    player = ai_user.player
    player.role = TOWN
    return player


@patch(
    "json.load",
    return_value={"discussion_analyser": "gpt-test", "webhook_url": "https://example.com"},
)
@patch("builtins.open", new_callable=mock_open, read_data='{"discussion_analyser": "gpt-test"}')
def build_turn_manager(
    _mock_file,
    _mock_json_load,
    participants: list[Player] | None = None,
    channel: discord.TextChannel | discord.Thread | None = None,
    bot: discord.Client | None = None,
    client=None,
) -> TurnManager:
    participants = participants or [_human_player(1, "Alice"), _ai_player("Bot")]
    channel = channel or MagicMock(spec=discord.TextChannel)
    channel.id = 123
    bot = bot or MagicMock(spec=discord.Client)
    client = client or MagicMock()
    return TurnManager(participants=participants, channel=channel, bot=bot, client=client)


def test_init_sets_core_state_and_defaults():
    participants = [_human_player(1, "Alice")]
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 456
    bot = MagicMock(spec=discord.Client)
    client = MagicMock()

    turn_manager = build_turn_manager(
        participants=participants,
        channel=channel,
        bot=bot,
        client=client,
    )

    assert turn_manager.participants is participants
    assert turn_manager.channel is channel
    assert turn_manager.bot is bot
    assert turn_manager.client is client
    assert turn_manager.running is False
    assert turn_manager.context == {}


def test_set_channel_updates_channel_reference():
    turn_manager = build_turn_manager(participants=[_human_player(1, "Alice")])
    new_channel = MagicMock(spec=discord.TextChannel)
    new_channel.id = 789

    turn_manager.set_channel(new_channel)

    assert turn_manager.channel is new_channel


def test_set_participants_replaces_participant_list():
    turn_manager = build_turn_manager(participants=[_human_player(1, "Alice")])
    new_participants = [_human_player(2, "Bob")]

    turn_manager.set_participants(new_participants)

    assert turn_manager.participants == new_participants


def test_set_context_replaces_ai_context():
    ai_player = _ai_player("Bot")
    turn_manager = build_turn_manager(participants=[ai_player])
    new_context = {ai_player.user: [{"role": "user", "content": "hello"}]}

    turn_manager.set_context(new_context)

    assert turn_manager.context == new_context


def test_broadcast_appends_message_to_all_ai_contexts():
    ai_one = _ai_player("Bot One")
    ai_two = _ai_player("Bot Two")
    human = _human_player(1, "Alice")
    turn_manager = build_turn_manager(participants=[human, ai_one, ai_two])

    turn_manager.broadcast("Night falls")

    assert turn_manager.context[ai_one.user][-1] == {"role": "user", "content": "Night falls"}
    assert turn_manager.context[ai_two.user][-1] == {"role": "user", "content": "Night falls"}


def test_broadcast_respects_exclude_player():
    ai_one = _ai_player("Bot One")
    ai_two = _ai_player("Bot Two")
    turn_manager = build_turn_manager(participants=[ai_one, ai_two])

    before_len_one = len(turn_manager.context[ai_one.user])
    before_len_two = len(turn_manager.context[ai_two.user])

    turn_manager.broadcast("Secret update", exclude=ai_two)

    assert len(turn_manager.context[ai_one.user]) == before_len_one + 1
    assert len(turn_manager.context[ai_two.user]) == before_len_two


def test_clean_ai_content_removes_think_blocks_and_markdown_inside_them():
    turn_manager = build_turn_manager(participants=[_human_player(1, "Alice")])

    cleaned = turn_manager._clean_ai_content(
        "  <think>## **private reasoning**</think>Visible answer  "
    )

    assert cleaned == "Visible answer"


def test_candidate_by_name_exact_match():
    alpha = _human_player(1, "Alpha")
    beta = _human_player(2, "Beta")
    turn_manager = build_turn_manager(participants=[alpha, beta])

    found = turn_manager._candidate_by_name([alpha, beta], "beta")

    assert found is beta


def test_candidate_by_name_returns_none_when_missing():
    alpha = _human_player(1, "Alpha")
    beta = _human_player(2, "Beta")
    turn_manager = build_turn_manager(participants=[alpha, beta])

    found = turn_manager._candidate_by_name([alpha, beta], "Gamma")

    assert found is None


@pytest.mark.asyncio
async def test_create_ai_completion_returns_clean_content_on_success():
    ai_player = _ai_player("Bot")

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="<think>hidden</think>Hello world"))]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    turn_manager = build_turn_manager(participants=[ai_player], client=client)

    result = await turn_manager.create_ai_completion(ai_player, "Say hello")

    assert result == "Hello world"
    assert turn_manager.context[ai_player.user][-1] == {
        "role": "assistant",
        "content": "Hello world",
    }
    client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_ai_completion_returns_empty_string_on_exception():
    ai_player = _ai_player("Bot")

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))

    turn_manager = build_turn_manager(participants=[ai_player], client=client)
    turn_manager.handle_player_failure = AsyncMock()

    result = await turn_manager.create_ai_completion(ai_player, "Prompt")

    assert result == ""
    turn_manager.handle_player_failure.assert_awaited_once_with(ai_player)


@pytest.mark.asyncio
async def test_on_message_queues_matching_author_when_running():
    human = _human_player(42, "Alice")
    turn_manager = build_turn_manager(participants=[human])
    turn_manager.running = True
    turn_manager.required_author = 42

    message = MagicMock(spec=discord.Message)
    message.author = MagicMock(spec=discord.Member)
    message.author.id = 42
    message.content = "I speak"

    await turn_manager.on_message(message)

    queued = turn_manager.message_queue.get_nowait()
    assert queued is message


@pytest.mark.asyncio
async def test_on_message_ignores_non_matching_author():
    human = _human_player(42, "Alice")
    turn_manager = build_turn_manager(participants=[human])
    turn_manager.required_author = 42

    message = MagicMock(spec=discord.Message)
    message.author = MagicMock(spec=discord.Member)
    message.author.id = 999
    message.content = "not allowed"

    await turn_manager.on_message(message)

    assert turn_manager.message_queue.empty()


def test_format_vote_details_formats_votes_and_abstain():
    alice = _human_player(1, "Alice")
    bob = _human_player(2, "Bob")
    turn_manager = build_turn_manager(participants=[alice, bob])

    votes = {1: "Alice", 2: "Abstain", 3: "Alice"}
    voter_names = {1: "VoterA", 2: "VoterB", 3: "VoterC"}

    details = turn_manager._format_vote_details(
        votes=votes,
        candidates=[alice, bob],
        voter_names=voter_names,
        allow_abstain=True,
    )

    assert "- Alice: VoterA, VoterC (2)" in details
    assert "- Abstain: VoterB (1)" in details


def test_format_vote_details_returns_no_votes_yet_when_empty():
    alice = _human_player(1, "Alice")
    bob = _human_player(2, "Bob")
    turn_manager = build_turn_manager(participants=[alice, bob])

    details = turn_manager._format_vote_details(
        votes={},
        candidates=[alice, bob],
        voter_names={},
        allow_abstain=False,
    )

    assert details == "No votes yet."
