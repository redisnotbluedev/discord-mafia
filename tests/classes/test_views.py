# pyright: reportMissingImports=false

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from classes.player import AIAbstraction, Player
from classes.roles import Role
from classes.views import (
    ABSTAIN_LABEL,
    ConfirmView,
    SpecialActionButton,
    SpecialActionsView,
    VoteSelect,
    VoteView,
)


def make_member(user_id: int, name: str = "User") -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    return member


def make_role(name: str, *, is_special: bool, can_act: bool = True) -> MagicMock:
    role = MagicMock(spec=Role)
    role.name = name
    role.is_special.return_value = is_special
    role.can_act.return_value = can_act
    role.get_button_info.return_value = {"label": f"{name} Action", "emoji": "✨"}
    role.handle_button_click = AsyncMock()
    return role


def make_interaction(user_id: int) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = make_member(user_id)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_confirm_view_init_stores_callbacks():
    yes = AsyncMock()
    no = AsyncMock()

    view = ConfirmView(yes, no)

    assert view.yes is yes
    assert view.no is no


@pytest.mark.asyncio
async def test_confirm_view_on_yes_calls_yes_callback():
    yes = AsyncMock()
    no = AsyncMock()
    interaction = make_interaction(1)
    view = ConfirmView(yes, no)

    await view.on_yes.callback(interaction)

    yes.assert_awaited_once_with(interaction)
    no.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_view_on_no_calls_no_callback():
    yes = AsyncMock()
    no = AsyncMock()
    interaction = make_interaction(2)
    view = ConfirmView(yes, no)

    await view.on_no.callback(interaction)

    no.assert_awaited_once_with(interaction)
    yes.assert_not_called()


@pytest.mark.asyncio
async def test_vote_view_init_stores_state_defaults():
    players = ["Alice", "Bob"]
    voter_names = {101: "Alice"}

    view = VoteView(players, allow_abstain=False, voter_names=voter_names)

    assert view.allow_abstain is False
    assert view.votes == {}
    assert view.required_votes == 0
    assert view.voter_names == voter_names
    assert view.player_names == players


@pytest.mark.asyncio
async def test_vote_view_contains_vote_select_and_no_abstain_by_default():
    view = VoteView(["Alice", "Bob"])

    selects = [item for item in view.children if isinstance(item, VoteSelect)]
    assert len(selects) == 1
    assert ABSTAIN_LABEL not in [opt.label for opt in selects[0].options]


@pytest.mark.asyncio
async def test_vote_select_init_creates_one_option_per_player():
    select = VoteSelect(["A", "B", "C"], "Vote", "🗳️", allow_abstain=False)

    assert len(select.options) == 3
    assert [opt.label for opt in select.options] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_vote_select_init_adds_abstain_option_when_enabled():
    select = VoteSelect(["A", "B"], "Vote", "🗳️", allow_abstain=True)

    labels = [opt.label for opt in select.options]
    assert len(labels) == 3
    assert labels[-1] == ABSTAIN_LABEL


@pytest.mark.asyncio
async def test_special_actions_view_tracks_players_and_adds_unique_special_role_buttons():
    doctor = make_role("Doctor", is_special=True)
    sheriff = make_role("Sheriff", is_special=True)
    town = make_role("Town", is_special=False)

    p1 = Player(make_member(1, "Doc"))
    p1.role = doctor
    p2 = Player(make_member(2, "Doc2"))
    p2.role = doctor
    p3 = Player(make_member(3, "Sheriff"))
    p3.role = sheriff
    p4 = Player(make_member(4, "Town"))
    p4.role = town

    alive_players = [p1, p2, p3, p4]
    view = SpecialActionsView(alive_players, MagicMock(), MagicMock())

    assert view.players == alive_players
    role_button_ids = sorted(
        item.custom_id
        for item in view.children
        if isinstance(item, SpecialActionButton) and item.custom_id is not None
    )
    assert role_button_ids == ["action_Doctor", "action_Sheriff"]


@pytest.mark.asyncio
async def test_special_actions_view_pending_humans_only_special_humans_who_can_act():
    doctor = make_role("Doctor", is_special=True, can_act=True)
    sheriff_blocked = make_role("Sheriff", is_special=True, can_act=False)
    town = make_role("Town", is_special=False, can_act=True)

    p1 = Player(make_member(10, "Doc"))
    p1.role = doctor
    p2 = Player(make_member(20, "Sheriff"))
    p2.role = sheriff_blocked
    p3 = Player(make_member(30, "Town"))
    p3.role = town
    p4 = Player(AIAbstraction("gpt-test", "AI"))
    p4.role = doctor

    view = SpecialActionsView([p1, p2, p3, p4], MagicMock(), MagicMock())

    assert view.pending_humans == {10}


@pytest.mark.asyncio
async def test_special_actions_view_get_returns_button_or_none():
    doctor = make_role("Doctor", is_special=True)
    p1 = Player(make_member(1, "Doc"))
    p1.role = doctor
    view = SpecialActionsView([p1], MagicMock(), MagicMock())

    assert view.get("action_Doctor") is not None
    assert view.get("does_not_exist") is None


@pytest.mark.asyncio
async def test_special_action_button_init_stores_role_and_custom_id():
    doctor = make_role("Doctor", is_special=True)

    button = SpecialActionButton(doctor)

    assert button.role is doctor
    assert button.custom_id == "action_Doctor"


@pytest.mark.asyncio
async def test_special_action_button_callback_rejects_non_matching_player():
    doctor = make_role("Doctor", is_special=True)
    player = Player(make_member(1, "Doc"))
    player.role = doctor
    view = SpecialActionsView([player], MagicMock(), MagicMock())
    button = view.get("action_Doctor")
    assert isinstance(button, SpecialActionButton)

    interaction = make_interaction(99)
    await button.callback(interaction)

    interaction.response.send_message.assert_awaited_once_with("Not for you.", ephemeral=True)


@pytest.mark.asyncio
async def test_special_action_button_callback_rejects_already_acted_player():
    doctor = make_role("Doctor", is_special=True)
    player = Player(make_member(1, "Doc"))
    player.role = doctor
    view = SpecialActionsView([player], MagicMock(), MagicMock())
    view.acted_players.add(1)
    button = view.get("action_Doctor")
    assert isinstance(button, SpecialActionButton)

    interaction = make_interaction(1)
    await button.callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        "You already performed your action!", ephemeral=True
    )


@pytest.mark.asyncio
async def test_special_action_button_callback_calls_role_handler_for_valid_player():
    doctor = make_role("Doctor", is_special=True)
    player = Player(make_member(1, "Doc"))
    player.role = doctor
    game = MagicMock()
    view = SpecialActionsView([player], MagicMock(), game)
    button = view.get("action_Doctor")
    assert isinstance(button, SpecialActionButton)

    interaction = make_interaction(1)
    await button.callback(interaction)

    doctor.handle_button_click.assert_awaited_once_with(game, player, interaction, action_view=view)
