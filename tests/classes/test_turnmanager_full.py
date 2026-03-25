import discord
import pytest
from typing import cast
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from classes.player import AIAbstraction, Player
from classes.roles import TOWN
from classes.turnmanager import TurnManager
from classes.views import VoteView
import tests.testutils as testutils


def _human_player(user_id: int, name: str) -> Player:
    return testutils.new_test_player(name, id=user_id, role=TOWN)


def _ai_player(name: str = "AI One", model: str = "gpt-test") -> Player:
    player = testutils.new_test_player(name, role=TOWN, is_ai=True)
    assert isinstance(player.user, AIAbstraction)
    player.user.model = model
    return player


@patch(
    "json.load",
    return_value={"discussion_analyser": "gpt-test", "webhook_url": "https://example.com"},
)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data='{"discussion_analyser": "gpt-test", "webhook_url": "https://example.com"}',
)
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
    ai_user = cast(AIAbstraction, ai_player.user)
    new_context: dict[AIAbstraction, list[dict[str, str]]] = {
        ai_user: [{"role": "user", "content": "hello"}]
    }

    turn_manager.set_context(new_context)

    assert turn_manager.context == new_context


def test_broadcast_appends_message_to_all_ai_contexts():
    ai_one = _ai_player("Bot One")
    ai_two = _ai_player("Bot Two")
    human = _human_player(1, "Alice")
    turn_manager = build_turn_manager(participants=[human, ai_one, ai_two])
    ai_one_user = cast(AIAbstraction, ai_one.user)
    ai_two_user = cast(AIAbstraction, ai_two.user)

    turn_manager.broadcast("Night falls")
    turn_manager.broadcast("Dawn breaks")

    assert turn_manager.context[ai_one_user][-2] == {"role": "user", "content": "Night falls"}
    assert turn_manager.context[ai_one_user][-1] == {"role": "user", "content": "Dawn breaks"}
    assert turn_manager.context[ai_two_user][-2] == {"role": "user", "content": "Night falls"}
    assert turn_manager.context[ai_two_user][-1] == {"role": "user", "content": "Dawn breaks"}


def test_broadcast_respects_exclude_player():
    ai_one = _ai_player("Bot One")
    ai_two = _ai_player("Bot Two")
    turn_manager = build_turn_manager(participants=[ai_one, ai_two])
    ai_one_user = cast(AIAbstraction, ai_one.user)
    ai_two_user = cast(AIAbstraction, ai_two.user)

    initial_len_one = len(turn_manager.context[ai_one_user])
    initial_len_two = len(turn_manager.context[ai_two_user])

    turn_manager.broadcast("Secret update", exclude=ai_two)

    assert len(turn_manager.context[ai_one_user]) == initial_len_one + 1
    assert turn_manager.context[ai_one_user][-1] == {"role": "user", "content": "Secret update"}
    assert len(turn_manager.context[ai_two_user]) == initial_len_two


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
    ai_user = cast(AIAbstraction, ai_player.user)

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="<think>hidden</think>Hello world"))]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    turn_manager = build_turn_manager(participants=[ai_player], client=client)

    result = await turn_manager.create_ai_completion(ai_player, "Say hello")

    assert result == "Hello world"
    assert turn_manager.context[ai_user][-1] == {
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


@pytest.mark.asyncio
async def test_initialize_ai_context_builds_system_prompts_for_ai_players_only():
    human = _human_player(1, "Alice")
    ai_one = _ai_player("Bot One")
    ai_two = _ai_player("Bot Two")

    turn_manager = build_turn_manager(participants=[human, ai_one, ai_two])
    context = turn_manager._initialize_ai_context([human, ai_one, ai_two])

    assert set(context.keys()) == {cast(AIAbstraction, ai_one.user), cast(AIAbstraction, ai_two.user)}
    prompt_one = context[cast(AIAbstraction, ai_one.user)][0]["content"]
    prompt_two = context[cast(AIAbstraction, ai_two.user)][0]["content"]
    assert "Your name is Bot One" in prompt_one
    assert "Players:" in prompt_one
    assert "Alice" in prompt_one
    assert "Bot Two" in prompt_one
    assert "There are [3] players" in prompt_one
    assert "Your name is Bot Two" in prompt_two
    assert "Bot One" in prompt_two


@pytest.mark.asyncio
async def test_get_next_speaker_parses_ai_mentions_and_excludes_speaker_and_dead_players():
    speaker = _human_player(1, "Speaker")
    asked = _human_player(2, "Asked")
    casual = _human_player(3, "Casual")
    dead = _human_player(4, "Ghost")
    dead.alive = False

    response = MagicMock()
    response.choices = [
        MagicMock(message=MagicMock(content="Asked:ASKED, Casual:CASUAL, Asked:ROLE, Speaker:ACCUSED, Ghost:ACCUSED"))
    ]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    turn_manager = build_turn_manager(participants=[speaker, asked, casual, dead], client=client)

    next_players = await turn_manager.get_next_speaker("Asked, what do you think?", speaker)

    assert next_players == [(asked, 2), (casual, 4)]


@pytest.mark.asyncio
async def test_run_round_cycles_human_and_ai_players():
    human = _human_player(1, "Alice")
    ai = _ai_player("Bot")

    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="<think>internal</think>AI speaks"))]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 123
    channel.set_permissions = AsyncMock()
    status_msg = MagicMock(spec=discord.Message)
    ai_status_msg = MagicMock(spec=discord.Message)
    final_ai_msg = MagicMock(spec=discord.Message)
    channel.send = AsyncMock(side_effect=[status_msg, ai_status_msg, final_ai_msg])

    bot = MagicMock(spec=discord.Client)
    turn_manager = build_turn_manager(participants=[human, ai], channel=channel, bot=bot, client=client)
    ai_user = cast(AIAbstraction, ai.user)
    initial_context_len = len(turn_manager.context[ai_user])

    human_message = MagicMock(spec=discord.Message)
    human_message.author = human.user
    human_message.content = "Human speaks"
    turn_manager.message_queue.get = AsyncMock(return_value=human_message)

    with patch("random.shuffle", side_effect=lambda seq: seq):
        await turn_manager.run_round(analyse=False, rounds=2)

    assert turn_manager.required_author == -1
    assert turn_manager.running is True
    client.chat.completions.create.assert_awaited_once()
    assert turn_manager.context[ai_user][initial_context_len] == {"role": "user", "content": "Alice: Human speaks"}
    assert turn_manager.context[ai_user][initial_context_len + 1] == {"role": "assistant", "content": "AI speaks"}
    assert any("it's your turn to speak" in call.args[0] for call in channel.send.await_args_list)
    assert any("**Bot:** AI speaks" in call.args[0] for call in channel.send.await_args_list)


@pytest.mark.asyncio
async def test_run_vote_sets_up_vote_view_and_returns_none_for_tie():
    ai_one = _ai_player("AI One")
    ai_two = _ai_player("AI Two")
    alice = _human_player(10, "Alice")
    bob = _human_player(20, "Bob")

    first_vote = MagicMock()
    first_vote.choices = [MagicMock(message=MagicMock(content="Alice"))]
    second_vote = MagicMock()
    second_vote.choices = [MagicMock(message=MagicMock(content="Bob"))]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=[first_vote, second_vote])

    poll = MagicMock(spec=discord.Message)
    poll.edit = AsyncMock()
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 999
    channel.send = AsyncMock(return_value=poll)

    turn_manager = build_turn_manager(participants=[ai_one, ai_two], channel=channel, client=client)

    winner = await turn_manager.run_vote(
        candidates=[alice, bob],
        message="Who should be eliminated?",
        timeout_s=0.01,
        break_ties_random=False,
    )

    assert winner is None
    send_kwargs = channel.send.await_args.kwargs
    assert isinstance(send_kwargs["view"], VoteView)
    assert send_kwargs["view"].player_names == ["Alice", "Bob"]
    assert send_kwargs["view"].required_votes == 0


@pytest.mark.asyncio
async def test_run_vote_breaks_ties_when_enabled():
    ai_one = _ai_player("AI One")
    ai_two = _ai_player("AI Two")
    alice = _human_player(10, "Alice")
    bob = _human_player(20, "Bob")

    first_vote = MagicMock()
    first_vote.choices = [MagicMock(message=MagicMock(content="Alice"))]
    second_vote = MagicMock()
    second_vote.choices = [MagicMock(message=MagicMock(content="Bob"))]

    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=[first_vote, second_vote])

    poll = MagicMock(spec=discord.Message)
    poll.edit = AsyncMock()
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 1000
    channel.send = AsyncMock(return_value=poll)

    turn_manager = build_turn_manager(participants=[ai_one, ai_two], channel=channel, client=client)

    with patch("random.choice", return_value="Alice"):
        winner = await turn_manager.run_vote(
            candidates=[alice, bob],
            message="Who should be eliminated?",
            timeout_s=0.01,
            break_ties_random=True,
        )

    assert winner is alice
