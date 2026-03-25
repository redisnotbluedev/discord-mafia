import pytest
from unittest.mock import AsyncMock, MagicMock

from classes.roles import (
    Alignment, Role, SelectRole, SaveRole, KillRole, InvestigateRole,
    ALL_ROLES, TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE, JESTER,
)

import tests.testutils as testutils


class TestAlignmentEnum:
    def test_town_value(self):
        assert Alignment.TOWN.value == "Town"

    def test_mafia_value(self):
        assert Alignment.MAFIA.value == "Mafia"

    def test_neutral_value(self):
        assert Alignment.NEUTRAL.value == "Neutral"


class TestRoleInit:
    def test_stores_name(self):
        r = Role("TestRole", Alignment.TOWN, "desc", "short")
        assert r.name == "TestRole"

    def test_stores_alignment(self):
        r = Role("TestRole", Alignment.TOWN, "desc", "short")
        assert r.alignment is Alignment.TOWN

    def test_stores_description(self):
        r = Role("TestRole", Alignment.TOWN, "full desc", "short")
        assert r.description == "full desc"

    def test_stores_short_description(self):
        r = Role("TestRole", Alignment.TOWN, "desc", "short desc")
        assert r.short_description == "short desc"

    def test_default_emoji(self):
        r = Role("TestRole", Alignment.TOWN, "desc", "short")
        assert r.emoji == "❓"

    def test_custom_emoji(self):
        r = Role("TestRole", Alignment.TOWN, "desc", "short", "🔥")
        assert r.emoji == "🔥"


class TestRoleMethods:
    def test_str_returns_name(self):
        r = Role("MyRole", Alignment.TOWN, "desc", "short")
        assert str(r) == "MyRole"

    def test_describe_returns_description(self):
        r = Role("R", Alignment.TOWN, "Full description", "short")
        assert r.describe() == "Full description"

    def test_is_special_returns_false(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        assert r.is_special() is False

    def test_night_action_type_returns_none(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        assert r.night_action_type() is None

    def test_get_button_info_label(self):
        r = Role("MyRole", Alignment.TOWN, "desc", "short", "🎯")
        assert r.get_button_info()["label"] == "MyRole"

    def test_get_button_info_emoji(self):
        r = Role("MyRole", Alignment.TOWN, "desc", "short", "🎯")
        assert r.get_button_info()["emoji"] == "🎯"

    def test_win_condition_returns_false(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        player = testutils.new_test_player()
        assert r.win_condition(player, [testutils.new_test_player()]) is False

    def test_get_prompt_uses_role_name(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        assert r.get_prompt() == "## R\nWhat do you want to do?"


class TestSelectRole:
    def test_is_special_returns_true(self):
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        assert r.is_special() is True

    def test_stores_action_label(self):
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "save")
        assert r.action_label == "save"

    def test_stores_skippable_true(self):
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act", skippable=True)
        assert r.skippable is True

    def test_skippable_defaults_false(self):
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        assert r.skippable is False

    def test_get_options_returns_alive_players(self):
        p1 = testutils.new_test_player("Alice")
        p2 = testutils.new_test_player("Bob")
        game = testutils.new_mock_game(players=[p1, p2])
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        options = r.get_options(game, testutils.new_test_player("Self"))
        assert p1 in options
        assert p2 in options

    def test_get_options_does_not_exclude_self(self):
        self_player = testutils.new_test_player("Self")
        game = testutils.new_mock_game(players=[self_player])
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        assert self_player in r.get_options(game, self_player)

    def test_get_options_excludes_dead_players(self):
        alive_p = testutils.new_test_player("Alive")
        dead_p = testutils.new_test_player("Dead", alive=False)
        game = testutils.new_mock_game(players=[alive_p, dead_p])
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        options = r.get_options(game, testutils.new_test_player("Self"))
        assert alive_p in options
        assert dead_p not in options

    def test_get_button_info_uses_role_name_and_emoji(self):
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        assert r.get_button_info() == {"label": "SR", "emoji": "🎯"}

    def test_get_prompt_uses_action_label(self):
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "investigate")
        assert r.get_prompt() == "## SR\nWho do you want to investigate?"

    async def test_handle_button_click_builds_select_view_and_sends_ephemeral(self, monkeypatch):
        import classes.views as views_module

        real_select_view = views_module.SelectView
        built: list[dict] = []

        class FakeSelectView(real_select_view):
            def __init__(self, options, callback):
                super().__init__(options, callback)
                built.append({"options": options, "callback": callback, "item": self})

        monkeypatch.setattr(views_module, "SelectView", FakeSelectView)

        p1 = testutils.new_test_player("Alice")
        p2 = testutils.new_test_player("Bob")
        game = testutils.new_mock_game(players=[p1, p2])
        player = testutils.new_test_player("Doctor")
        interaction = testutils.new_mock_interaction()
        action_view = MagicMock()

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save", skippable=True)
        await r.handle_button_click(game, player, interaction, action_view)

        assert len(built) == 1
        assert [opt.label for opt in built[0]["options"]] == ["Alice", "Bob", "Abstain"]
        assert [opt.value for opt in built[0]["options"]] == ["0", "1", "abstain"]
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args_list[0]
        assert args[0] == "## Doc\nWho do you want to save?"
        assert kwargs["ephemeral"] is True
        assert isinstance(kwargs["view"], FakeSelectView)

    async def test_on_selected_handles_selection_and_marks_player_acted(self):
        game = testutils.new_mock_game()
        player = testutils.new_test_player("Doctor", id=111)
        target = testutils.new_test_player("Alice")
        interaction = testutils.new_mock_interaction(user_id=111)
        interaction.data = {"values": ["0"]}
        action_view = MagicMock()
        action_view.acted_players = set()
        action_view.pending_humans = {111}

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save")
        r.handle_selection = AsyncMock()

        await r.on_selected(game, player, interaction, [target], action_view)

        r.handle_selection.assert_awaited_once_with(game, player, target)
        interaction.response.edit_message.assert_awaited_once_with(
            content="You chose to save Alice.",
            view=None,
        )
        assert 111 in action_view.acted_players
        assert 111 not in action_view.pending_humans

    async def test_on_selected_abstain_marks_player_acted(self):
        game = testutils.new_mock_game()
        player = testutils.new_test_player("Doctor", id=111)
        interaction = testutils.new_mock_interaction(user_id=111)
        interaction.data = {"values": ["abstain"]}
        action_view = MagicMock()
        action_view.acted_players = set()
        action_view.pending_humans = {111}

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save", skippable=True)
        r.handle_selection = AsyncMock()

        await r.on_selected(game, player, interaction, [], action_view)

        r.handle_selection.assert_not_called()
        interaction.response.edit_message.assert_awaited_once_with(
            content="You chose to abstain.",
            view=None,
        )
        assert 111 in action_view.acted_players
        assert 111 not in action_view.pending_humans

    async def test_on_selected_blocks_double_act_when_called_twice(self):
        game = testutils.new_mock_game()
        player = testutils.new_test_player("Doctor", id=111)
        target = testutils.new_test_player("Alice")

        interaction_first = testutils.new_mock_interaction(user_id=111)
        interaction_first.data = {"values": ["0"]}
        interaction_second = testutils.new_mock_interaction(user_id=111)
        interaction_second.data = {"values": ["0"]}

        action_view = MagicMock()
        action_view.acted_players = set()
        action_view.pending_humans = {111}

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save")
        r.handle_selection = AsyncMock()

        await r.on_selected(game, player, interaction_first, [target], action_view)
        await r.on_selected(game, player, interaction_second, [target], action_view)

        r.handle_selection.assert_awaited_once_with(game, player, target)
        interaction_second.response.edit_message.assert_awaited_once_with(
            content="You have already performed your action!",
            view=None,
        )

    async def test_night_action_ai_picks_correct_player_without_mocking_extract_choice(self):
        alice = testutils.new_test_player("Alice")
        bob = testutils.new_test_player("Bob")
        game = testutils.new_mock_game(players=[alice, bob])
        game.turns.create_ai_completion = AsyncMock(return_value="I choose Alice")

        ai_player = testutils.new_test_player("Doctor")

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save")
        r.get_options = MagicMock(return_value=[alice, bob])
        r.handle_selection = AsyncMock()

        await r.night_action_ai(game, ai_player)

        game.turns.create_ai_completion.assert_awaited_once()
        r.handle_selection.assert_awaited_once_with(game, ai_player, alice)


class TestSaveRole:
    def test_night_action_type_is_save(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        assert r.night_action_type() == "save"

    def test_is_special_returns_true(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        assert r.is_special() is True

    async def test_handle_selection_appends_to_saves(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = testutils.new_test_player("Doctor")
        target = testutils.new_test_player("Target")
        game = testutils.new_mock_game(players=[player, target])
        await r.handle_selection(game, player, target)
        assert target in game.night_actions["saves"]

    async def test_handle_selection_tracks_pending_save(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = testutils.new_test_player("Doctor")
        target = testutils.new_test_player("Target")
        game = testutils.new_mock_game(players=[player, target])
        await r.handle_selection(game, player, target)
        assert player.role_state["pending_save"] is target

    async def test_handle_selection_replaces_previous_save(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = testutils.new_test_player("Doctor")
        old_target = testutils.new_test_player("OldTarget")
        new_target = testutils.new_test_player("NewTarget")
        game = testutils.new_mock_game(players=[player, old_target, new_target])
        await r.handle_selection(game, player, old_target)
        await r.handle_selection(game, player, new_target)
        assert old_target not in game.night_actions["saves"]
        assert new_target in game.night_actions["saves"]
        assert player.role_state["pending_save"] is new_target

    async def test_on_night_end_moves_pending_to_last_saved(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = testutils.new_test_player("Doctor")
        target = testutils.new_test_player("Target")
        game = testutils.new_mock_game(players=[player, target])
        player.role_state["pending_save"] = target
        await r.on_night_end(game, player)
        assert player.role_state["last_saved"] is target
        assert player.role_state["pending_save"] is None

    async def test_on_night_end_last_saved_none_when_no_pending(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = testutils.new_test_player("Doctor")
        game = testutils.new_mock_game(players=[player])
        await r.on_night_end(game, player)
        assert player.role_state["last_saved"] is None
        assert player.role_state["pending_save"] is None


class TestKillRole:
    def test_night_action_type_is_kill(self):
        r = KillRole("Killer", Alignment.MAFIA, "desc", "short")
        assert r.night_action_type() == "kill"

    def test_is_special_returns_true(self):
        r = KillRole("Killer", Alignment.MAFIA, "desc", "short")
        assert r.is_special() is True

    async def test_handle_selection_appends_to_kills(self):
        r = KillRole("Killer", Alignment.MAFIA, "desc", "short")
        player = testutils.new_test_player("Killer")
        target = testutils.new_test_player("Victim")
        game = testutils.new_mock_game(players=[player, target])
        await r.handle_selection(game, player, target)
        assert target in game.night_actions["kills"]

    async def test_handle_selection_multiple_kills_appended(self):
        r = KillRole("Killer", Alignment.MAFIA, "desc", "short")
        player = testutils.new_test_player("Killer")
        t1 = testutils.new_test_player("Victim1")
        t2 = testutils.new_test_player("Victim2")
        game = testutils.new_mock_game(players=[player, t1, t2])
        await r.handle_selection(game, player, t1)
        await r.handle_selection(game, player, t2)
        assert t1 in game.night_actions["kills"]
        assert t2 in game.night_actions["kills"]


class TestInvestigateRole:
    def test_night_action_type_is_investigate(self):
        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        assert r.night_action_type() == "investigate"

    def test_get_options_excludes_self(self):
        self_player = testutils.new_test_player("Self")
        other = testutils.new_test_player("Other")
        game = testutils.new_mock_game(players=[self_player, other])
        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        options = r.get_options(game, self_player)
        assert self_player not in options
        assert other in options

    def test_get_options_excludes_dead_players(self):
        self_player = testutils.new_test_player("Self")
        alive = testutils.new_test_player("Alive")
        dead = testutils.new_test_player("Dead", alive=False)
        game = testutils.new_mock_game(players=[self_player, alive, dead])
        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        options = r.get_options(game, self_player)
        assert alive in options
        assert dead not in options

    async def test_on_selected_shows_alignment_in_response(self):
        game = testutils.new_mock_game()
        player = testutils.new_test_player("Sheriff", id=111)
        suspect = testutils.new_test_player("Alice")
        suspect.role = MAFIA
        interaction = testutils.new_mock_interaction(user_id=111)
        interaction.data = {"values": ["0"]}
        action_view = MagicMock()
        action_view.acted_players = set()
        action_view.pending_humans = {111}

        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        r.handle_selection = AsyncMock()

        await r.on_selected(game, player, interaction, [suspect], action_view)

        r.handle_selection.assert_awaited_once_with(game, player, suspect)
        interaction.response.edit_message.assert_awaited_once_with(
            content="You chose to investigate Alice. Alice is **MAFIA**!",
            view=None,
        )
        assert 111 in action_view.acted_players
        assert 111 not in action_view.pending_humans

    async def test_handle_selection_sends_result_to_ai_player(self):
        from classes.player import AIAbstraction

        game = testutils.new_mock_game()
        game.turns.create_ai_completion = AsyncMock()
        player = testutils.new_test_player("Sheriff")
        player.user = AIAbstraction("gpt-4o-mini", "Bot")
        suspect = testutils.new_test_player("Alice")
        suspect.role = TOWN

        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        await r.handle_selection(game, player, suspect)

        game.turns.create_ai_completion.assert_awaited_once_with(
            player,
            "Alice is **TOWN**.",
        )
