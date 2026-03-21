import pytest  # type: ignore[reportMissingImports]
from unittest.mock import AsyncMock, MagicMock

from classes.roles import (
    Alignment, Role, SelectRole, SaveRole, KillRole, InvestigateRole,
    NEUTRAL, ALL_ROLES, TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE, JESTER,
)


def make_player(name="Alice", alive=True):
    p = MagicMock()
    p.name = name
    p.alive = alive
    p.role_state = {}
    return p


def make_game(players):
    game = MagicMock()
    game.get_alive_players.return_value = players
    game.night_actions = {}
    return game


class TestAlignmentEnum:
    def test_town_value(self):
        assert Alignment.TOWN.value == "Town"

    def test_mafia_value(self):
        assert Alignment.MAFIA.value == "Mafia"

    def test_neutral_value(self):
        assert Alignment.NEUTRAL.value == "Neutral"

    def test_module_neutral_is_alignment_neutral(self):
        assert NEUTRAL is Alignment.NEUTRAL


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


class TestRoleDunder:
    def test_str_returns_name(self):
        r = Role("MyRole", Alignment.TOWN, "desc", "short")
        assert str(r) == "MyRole"

    def test_eq_same_name_different_desc(self):
        r1 = Role("Same", Alignment.TOWN, "desc1", "short1")
        r2 = Role("Same", Alignment.MAFIA, "desc2", "short2")
        assert r1 == r2

    def test_eq_different_name(self):
        r1 = Role("Alpha", Alignment.TOWN, "desc", "short")
        r2 = Role("Beta", Alignment.TOWN, "desc", "short")
        assert r1 != r2

    def test_eq_non_role_returns_false(self):
        r = Role("MyRole", Alignment.TOWN, "desc", "short")
        assert r != "MyRole"

    def test_hash_equals_hash_of_name(self):
        r = Role("MyRole", Alignment.TOWN, "desc", "short")
        assert hash(r) == hash("MyRole")

    def test_hash_consistent_with_eq(self):
        r1 = Role("Same", Alignment.TOWN, "desc1", "short1")
        r2 = Role("Same", Alignment.MAFIA, "desc2", "short2")
        assert hash(r1) == hash(r2)


class TestRoleMethods:
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

    def test_can_act_returns_true(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        assert r.can_act(MagicMock()) is True

    def test_win_condition_returns_false(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        assert r.win_condition(MagicMock(), [MagicMock()]) is False

    def test_get_prompt_uses_role_name(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        assert r.get_prompt() == "## R\nWhat do you want to do?"

    async def test_handle_button_click_noop(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        await r.handle_button_click(MagicMock(), MagicMock(), MagicMock())

    async def test_on_night_end_noop(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        await r.on_night_end(MagicMock(), MagicMock())

    async def test_night_action_ai_noop(self):
        r = Role("R", Alignment.TOWN, "desc", "short")
        await r.night_action_ai(MagicMock(), MagicMock())


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
        p1 = make_player("Alice", alive=True)
        p2 = make_player("Bob", alive=True)
        game = make_game([p1, p2])
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        options = r.get_options(game, make_player("Self"))
        assert p1 in options
        assert p2 in options

    def test_get_options_does_not_exclude_self(self):
        self_player = make_player("Self", alive=True)
        game = make_game([self_player])
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        assert self_player in r.get_options(game, self_player)

    def test_get_options_excludes_dead_players(self):
        alive_p = make_player("Alive", alive=True)
        dead_p = make_player("Dead", alive=False)
        game = make_game([alive_p, dead_p])
        r = SelectRole("SR", Alignment.TOWN, "desc", "short", "🎯", "act")
        options = r.get_options(game, make_player("Self"))
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

        built = {}

        class FakeSelectView:
            def __init__(self, options, callback):
                built["options"] = options
                built["callback"] = callback

        monkeypatch.setattr(views_module, "SelectView", FakeSelectView)

        p1 = make_player("Alice", alive=True)
        p2 = make_player("Bob", alive=True)
        game = make_game([p1, p2])
        player = make_player("Doctor", alive=True)
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        action_view = MagicMock()

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save", skippable=True)
        await r.handle_button_click(game, player, interaction, action_view)

        assert [opt.label for opt in built["options"]] == ["Alice", "Bob", "Abstain"]
        assert [opt.value for opt in built["options"]] == ["0", "1", "abstain"]
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.await_args_list[0]
        assert args[0] == "## Doc\nWho do you want to save?"
        assert kwargs["ephemeral"] is True
        assert isinstance(kwargs["view"], FakeSelectView)

    async def test_on_selected_handles_selection_and_marks_player_acted(self):
        game = make_game([])
        player = make_player("Doctor")
        target = make_player("Alice")
        interaction = MagicMock()
        interaction.data = {"values": ["0"]}
        interaction.user.id = 111
        interaction.response.edit_message = AsyncMock()
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
        game = make_game([])
        player = make_player("Doctor")
        interaction = MagicMock()
        interaction.data = {"values": ["abstain"]}
        interaction.user.id = 111
        interaction.response.edit_message = AsyncMock()
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

    async def test_on_selected_when_already_acted_sends_warning(self):
        game = make_game([])
        player = make_player("Doctor")
        target = make_player("Alice")
        interaction = MagicMock()
        interaction.data = {"values": ["0"]}
        interaction.user.id = 111
        interaction.response.edit_message = AsyncMock()
        action_view = MagicMock()
        action_view.acted_players = {111}
        action_view.pending_humans = {111}

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save")
        r.handle_selection = AsyncMock()

        await r.on_selected(game, player, interaction, [target], action_view)

        r.handle_selection.assert_not_called()
        interaction.response.edit_message.assert_awaited_once_with(
            content="You have already performed your action!",
            view=None,
        )

    async def test_night_action_ai_uses_extract_choice_and_handles_selection(self, monkeypatch):
        from classes import roles as roles_module

        ai_player = make_player("Doctor")
        target = make_player("Alice")
        game = make_game([target])
        game.turns = MagicMock()
        game.turns.create_ai_completion = AsyncMock(return_value="I choose Alice")

        r = SelectRole("Doc", Alignment.TOWN, "desc", "short", "🎯", "save")
        r.get_options = MagicMock(return_value=[target])
        r.handle_selection = AsyncMock()
        extract_choice_mock = MagicMock(return_value="Alice")
        monkeypatch.setattr(roles_module, "extract_choice", extract_choice_mock)

        await r.night_action_ai(game, ai_player)

        game.turns.create_ai_completion.assert_awaited_once()
        extract_choice_mock.assert_called_once_with("I choose Alice", ["Alice"])
        r.handle_selection.assert_awaited_once_with(game, ai_player, target)


class TestSaveRole:
    def test_night_action_type_is_save(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        assert r.night_action_type() == "save"

    def test_is_special_returns_true(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        assert r.is_special() is True

    async def test_handle_selection_appends_to_saves(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = make_player("Doctor")
        target = make_player("Target")
        game = make_game([player, target])
        await r.handle_selection(game, player, target)
        assert target in game.night_actions["saves"]

    async def test_handle_selection_tracks_pending_save(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = make_player("Doctor")
        target = make_player("Target")
        game = make_game([player, target])
        await r.handle_selection(game, player, target)
        assert player.role_state["pending_save"] is target

    async def test_handle_selection_replaces_previous_save(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = make_player("Doctor")
        old_target = make_player("OldTarget")
        new_target = make_player("NewTarget")
        game = make_game([player, old_target, new_target])
        await r.handle_selection(game, player, old_target)
        await r.handle_selection(game, player, new_target)
        assert old_target not in game.night_actions["saves"]
        assert new_target in game.night_actions["saves"]

    async def test_on_night_end_moves_pending_to_last_saved(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = make_player("Doctor")
        target = make_player("Target")
        game = make_game([player, target])
        player.role_state["pending_save"] = target
        await r.on_night_end(game, player)
        assert player.role_state["last_saved"] is target
        assert player.role_state["pending_save"] is None

    async def test_on_night_end_last_saved_none_when_no_pending(self):
        r = SaveRole("Doc", Alignment.TOWN, "desc", "short")
        player = make_player("Doctor")
        game = make_game([player])
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
        player = make_player("Killer")
        target = make_player("Victim")
        game = make_game([player, target])
        await r.handle_selection(game, player, target)
        assert target in game.night_actions["kills"]

    async def test_handle_selection_multiple_kills_appended(self):
        r = KillRole("Killer", Alignment.MAFIA, "desc", "short")
        player = make_player("Killer")
        t1 = make_player("Victim1")
        t2 = make_player("Victim2")
        game = make_game([player, t1, t2])
        await r.handle_selection(game, player, t1)
        await r.handle_selection(game, player, t2)
        assert t1 in game.night_actions["kills"]
        assert t2 in game.night_actions["kills"]


class TestInvestigateRole:
    def test_night_action_type_is_investigate(self):
        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        assert r.night_action_type() == "investigate"

    def test_get_options_excludes_self(self):
        self_player = make_player("Self", alive=True)
        other = make_player("Other", alive=True)
        game = make_game([self_player, other])
        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        options = r.get_options(game, self_player)
        assert self_player not in options
        assert other in options

    def test_get_options_excludes_dead_players(self):
        self_player = make_player("Self", alive=True)
        alive = make_player("Alive", alive=True)
        dead = make_player("Dead", alive=False)
        game = make_game([self_player, alive, dead])
        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        options = r.get_options(game, self_player)
        assert alive in options
        assert dead not in options

    async def test_on_selected_shows_alignment_in_response(self):
        game = make_game([])
        player = make_player("Sheriff")
        suspect = make_player("Alice")
        suspect.role = MagicMock(alignment=Alignment.MAFIA)
        interaction = MagicMock()
        interaction.data = {"values": ["0"]}
        interaction.response.edit_message = AsyncMock()

        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        r.handle_selection = AsyncMock()

        await r.on_selected(game, player, interaction, [suspect])

        r.handle_selection.assert_awaited_once_with(game, player, suspect)
        interaction.response.edit_message.assert_awaited_once_with(
            content="You chose to investigate Alice. Alice is **MAFIA**!",
            view=None,
        )

    async def test_handle_selection_sends_result_to_ai_player(self):
        from classes.player import AIAbstraction

        game = make_game([])
        game.turns = MagicMock()
        game.turns.create_ai_completion = AsyncMock()
        player = make_player("Sheriff")
        player.user = AIAbstraction("gpt-4o-mini", "Bot")
        suspect = make_player("Alice")
        suspect.role = MagicMock(alignment=Alignment.TOWN)

        r = InvestigateRole("Sheriff", Alignment.TOWN, "desc", "short")
        await r.handle_selection(game, player, suspect)

        game.turns.create_ai_completion.assert_awaited_once_with(
            player,
            "Alice is **TOWN**.",
        )


class TestAllRoles:
    def test_all_roles_has_six_entries(self):
        assert len(ALL_ROLES) == 6

    def test_all_roles_exact_order(self):
        assert ALL_ROLES == [TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE, JESTER]

    def test_town_name(self):
        assert TOWN.name == "Town"

    def test_town_alignment(self):
        assert TOWN.alignment is Alignment.TOWN

    def test_mafia_name(self):
        assert MAFIA.name == "Mafia"

    def test_mafia_alignment(self):
        assert MAFIA.alignment is Alignment.MAFIA

    def test_doctor_name(self):
        assert DOCTOR.name == "Doctor"

    def test_doctor_alignment(self):
        assert DOCTOR.alignment is Alignment.TOWN

    def test_sheriff_name(self):
        assert SHERIFF.name == "Sheriff"

    def test_sheriff_alignment(self):
        assert SHERIFF.alignment is Alignment.TOWN

    def test_vigilante_name(self):
        assert VIGILANTE.name == "Vigilante"

    def test_vigilante_alignment(self):
        assert VIGILANTE.alignment is Alignment.TOWN

    def test_jester_name(self):
        assert JESTER.name == "Jester"

    def test_jester_alignment(self):
        assert JESTER.alignment is Alignment.NEUTRAL
