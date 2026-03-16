"""Role system for Mafia game.

Defines abstract categories of roles, which are inherited by specific
role implementations.

Role instances are module-level singletons (TOWN, MAFIA, DOCTOR, etc.)
shared across all games.  Per-player state is stored in Player.role_state,
not in the Role instances themselves.
"""

from enum import Enum
from typing import TYPE_CHECKING, Literal, TypedDict, cast

import discord


if TYPE_CHECKING:
	from classes.game import MafiaGame
	from classes.player import Player
	from classes.views import SpecialActionsView
	# PYREX NOTE: discord.types.interactions is _explicitly_
	# not a public interface, because discord.py is a great library
	#
	# However -- the relevant type is st ill part of the public interface
	# So, I still think we should import this because I think we deeply want
	# an explicit compile failure if they (for some ungodly reason) change this
	#
	# (https://github.com/Rapptz/discord.py/issues/9653#issuecomment-1822374218)
	# (https://github.com/Rapptz/discord.py/issues/9653#issuecomment-1822374218)
	from discord.types.interactions import SelectMessageComponentInteractionData



class Alignment(Enum):
	"""Faction alignment.  Used for win condition checks and UI grouping."""
	TOWN = "Town"
	MAFIA = "Mafia"
	NEUTRAL = "Neutral"

NEUTRAL = Alignment.NEUTRAL


class ButtonInfo(TypedDict):
	label: str
	emoji: str


class Role:
	"""Base class for all game roles.

	Roles are module-level singletons.  Override is_special() to return
	True for roles with night actions, and implement handle_button_click()
	and night_action_ai() for the actual action logic.

	Attributes:
		name: Display name (e.g. 'Doctor').
		alignment: Alignment.TOWN, MAFIA, or NEUTRAL.
		description: Full role description shown to the player.
		short_description: One-line description for the settings select.
		emoji: Emoji used in buttons and select options.
	"""

	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str, emoji: str = "❓"):
		self.name = name
		self.alignment = alignment
		self.description = description
		self.short_description = short_description
		self.emoji = emoji

	def __str__(self) -> str:
		return self.name

	def __eq__(self, other: object) -> bool:
		"""Compares roles by name."""
		if isinstance(other, Role):
			return self.name == other.name
		return False

	def __hash__(self) -> int:
		"""Returns the hash of the role name."""
		return hash(self.name)

	def describe(self) -> str:
		"""Return the full role description text."""
		return self.description

	def is_special(self) -> bool:
		"""Return True if this role has a night action."""
		return False

	def night_action_type(self) -> Literal["save", "kill", "investigate", None]:
		"""Return the action type string ('save', 'kill', 'investigate'), or None."""
		return None

	def get_button_info(self) -> ButtonInfo:
		"""Return a dict for labeling a button with this role."""
		return {"label": self.name, "emoji": self.emoji}

	def get_prompt(self) -> str:
		"""Return a prompt inviting the player to act."""
		return f"## {self.name}\nWhat do you want to do?"

	async def handle_button_click(self, game: "MafiaGame", player: "Player", interaction: discord.Interaction, action_view: "SpecialActionsView | None"=None):
		"""Handle a human player clicking their night action button.  No-op for base Role."""
		pass

	async def on_night_end(self, game: "MafiaGame", player: "Player"):
		"""Called after night resolution.  Used by roles that track state across nights."""
		pass

	async def night_action_ai(self, game: "MafiaGame", player: "Player"):
		"""Execute the night action for an AI player.  No-op for base Role."""
		pass

	def can_act(self, player: "Player") -> bool:
		"""Return whether this player can use their special action, if any.

		Used to identify whether a player has skipped their turn
		because they had no action available. A player who repeatedly
		skips for *no* good reason will eventually be modkilled.
		"""
		return True

	def win_condition(self, player: "Player", players: list["Player"]) -> bool:
		"""Check if this player has won due to their special ability."""
		return False

class SelectRole(Role):
	"""Role with a target-selection night action (choose a player to act on).

	Provides the common UI flow: button click → select menu → on_selected →
	handle_selection.  Subclasses override handle_selection() to implement
	the actual effect.

	Also provides night_action_ai() which prompts the AI to choose a target.
	"""

	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str, emoji: str, action_label: str, skippable: bool = False):
		"""Initialize a SelectRole.

		Args:
			name: Display name (e.g. 'Doctor').
			alignment: Alignment.TOWN, MAFIA, or NEUTRAL.
			description: Full role description shown to the player.
			short_description: One-line description for the settings select.
			emoji: Emoji used in buttons and select options.
			action_label: String describing the action (e.g. 'save', 'kill', 'investigate').
			skippable: Whether the player can choose to abstain from acting.
		"""
		super().__init__(name, alignment, description, short_description)
		self.emoji = emoji
		self.action_label = action_label
		self.skippable = skippable

	def is_special(self) -> bool:
		return True

	def get_button_info(self) -> ButtonInfo:
		return {"label": self.name, "emoji": self.emoji}

	def get_prompt(self) -> str:
		return f"## {self.name}\nWho do you want to {self.action_label}?"

	def get_options(self, game: "MafiaGame", player: "Player") -> "list[Player]":
		return [p for p in game.get_alive_players() if p.alive]

	async def handle_button_click(self, game: "MafiaGame", player: "Player", interaction: discord.Interaction, action_view: "SpecialActionsView | None"=None) -> None:
		"""Show a select menu of valid targets for this role's night action."""
		import discord
		from classes.views import SelectView
		options = self.get_options(game, player)
		select_options = [
			discord.SelectOption(label=p.name, value=str(i), emoji=self.emoji)
			for i, p in enumerate(options)
		]

		if self.skippable:
			select_options.append(discord.SelectOption(label="Abstain", value="abstain", emoji="⏭️"))

		select_view = SelectView(select_options, lambda inter: self.on_selected(game, player, inter, options, action_view))
		await interaction.response.send_message(self.get_prompt(), view=select_view, ephemeral=True)

	async def on_selected(self, game: "MafiaGame", player: "Player", interaction: discord.Interaction, options: "list[Player]", action_view: "SpecialActionsView | None"=None) -> None:
		"""Handle the human player's target selection from the select menu.

		Marks the player as having acted and delegates to handle_selection().
		"""
		if action_view and interaction.user.id in action_view.acted_players:
			await interaction.response.edit_message(content="You have already performed your action!", view=None)
			return

		# PYREX NOTE: It's not clear, but the previous data types in this code
		# imply that this is probably the implicit cast that was meant
		data = cast(SelectMessageComponentInteractionData, interaction.data)
		selection = data['values'][0]
		if selection == "abstain":
			await interaction.response.edit_message(content=f"You chose to abstain.", view=None)
			if action_view:
				action_view.acted_players.add(interaction.user.id)
				action_view.pending_humans.discard(interaction.user.id)
			return

		user = options[int(selection)]
		await self.handle_selection(game, player, user)
		await interaction.response.edit_message(content=f"You chose to {self.action_label} {user.name}.", view=None)
		if action_view:
			action_view.acted_players.add(interaction.user.id)
			action_view.pending_humans.discard(interaction.user.id)

	async def handle_selection(self, game: "MafiaGame", player: "Player", user: "Player") -> None:
		"""Apply the role's effect to the chosen target.  Override in subclasses.

		Common path between on_selected and night_action_ai.
		"""
		pass

	async def night_action_ai(self, game: "MafiaGame", player: "Player") -> None:
		"""Prompt the AI to choose a target and apply the role's effect."""

		options = self.get_options(game, player)
		opt_names = [p.name for p in options]
		prompt_options = opt_names.copy()
		if self.skippable:
			prompt_options.append("abstain")

		prompt = f"NIGHT: {self.name.upper()} {self.action_label.upper()}\n> {self.get_prompt()}\n"
		if self.skippable:
			prompt += "Note: You are NOT required to act. If you don't have a strong suspicion, you should 'abstain' to avoid hurting your team.\n"
		prompt += "Available options:\n" + "\n".join([f"- {name}" for name in prompt_options])

		assert game.turns is not None
		choice_text = await game.turns.create_ai_completion(player, prompt)

		if not choice_text:
			return

		if self.skippable and 'abstain' in choice_text.lower():
			return

		chosen_name = game.turns.extract_choice(choice_text, opt_names)
		chosen = None
		if chosen_name:
			chosen = next((p for p in options if p.name == chosen_name), None)

		if not chosen:
			if self.skippable:
				return
			import random
			chosen = random.choice(options)

		if chosen:
			await self.handle_selection(game, player, chosen)

class SaveRole(SelectRole):
	"""Role that can protect a player from being killed."""

	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str):
		super().__init__(name, alignment, description, short_description, "🧑‍⚕️", "save", skippable=False)

	def night_action_type(self) -> Literal["save"]:
		return "save"

	async def handle_selection(self, game: "MafiaGame", player: "Player", user: "Player") -> None:
		saves = game.night_actions.setdefault("saves", [])
		old_save = player.role_state.get("pending_save")
		if old_save and old_save in saves:
			saves.remove(old_save)

		saves.append(user)
		player.role_state["pending_save"] = user

	async def on_night_end(self, game: "MafiaGame", player: "Player") -> None:
		player.role_state["last_saved"] = player.role_state.get("pending_save")
		player.role_state["pending_save"] = None

class KillRole(SelectRole):
	"""Role that can kill a player during the night."""

	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str, skippable: bool = False):
		super().__init__(name, alignment, description, short_description, "🔫", "kill", skippable=skippable)

	def night_action_type(self) -> Literal["kill"]:
		return "kill"

	async def handle_selection(self, game: "MafiaGame", player: "Player", user: "Player") -> None:
		game.night_actions.setdefault("kills", []).append(user)

class InvestigateRole(SelectRole):
	"""Role that can investigate a player's alignment (Sheriff).

	Note: on_selected() has a different signature from SelectRole.on_selected()
	(missing action_view parameter), but this method is never actually called
	because handle_button_click() binds the callback to SelectRole.on_selected
	via the lambda.
	"""

	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str):
		super().__init__(name, alignment, description, short_description, "🕵️", "investigate", skippable=False)

	def night_action_type(self) -> Literal["investigate"]:
		return "investigate"

	def get_options(self, game: "MafiaGame", player: "Player"):
		return [p for p in game.get_alive_players() if p.alive and p != player]

	# PYREX NOTE: As AdamNorberg points out, this type is wrong for the prototype. Ignoring for now!
	async def on_selected(self, game: "MafiaGame", player: "Player", interaction: discord.Interaction, options: "list[Player]") -> None:  # type: ignore[reportIncompatibleMethodOverride] # <- Sorry if this breaks anyone's type checking, I'm not using Pyright
		"""Handle the human player's target selection from the select menu.

		The prototype of this function is incompatible with
		`SelectRole.on_selected` -- the `action_view` parameter is missing.
		This function is not reached, however, because `handle_button_click`
		specifically binds to `SelectRole.on_selected` via a lambda.
		"""
		# PYREX NOTE: This is, again, the type implied by the use site!
		data = cast(SelectMessageComponentInteractionData, interaction.data)
		selection = data['values'][0]
		user = options[int(selection)]
		await self.handle_selection(game, player, user)

		# PYREX NOTE: Tacit assumption made by the existing code pre-typechecking
		assert user.role is not None, "role was unexpectedly None"
		await interaction.response.edit_message(content=f"You chose to investigate {user.name}. {user.name} is **{user.role.alignment.value.upper()}**!", view=None)

	async def handle_selection(self, game, player, user):
		# PYREX NOTE: Tacit assumption made by the existing code pre-typechecking
		assert game.turns is not None
		assert user.role is not None, "role was unexpectedly None"
		result_prompt = f"{user.name} is **{user.role.alignment.value.upper()}**."
		from classes.player import AIAbstraction
		if isinstance(player.user, AIAbstraction):
			await game.turns.create_ai_completion(player, result_prompt)

from .townsperson import Town, TOWN
from .mafia import Mafia, MAFIA
from .doctor import Doctor, DOCTOR
from .sheriff import Sheriff, SHERIFF
from .vigilante import Vigilante, VIGILANTE
from .jester import Jester, JESTER

ALL_ROLES = [TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE, JESTER]

__all__ = ['Alignment', 'Role', 'SaveRole', 'KillRole', 'InvestigateRole', 'Town', 'Mafia', 'Doctor', 'Sheriff', 'Vigilante', 'Jester', 'TOWN', 'MAFIA', 'DOCTOR', 'SHERIFF', 'VIGILANTE', 'JESTER', 'NEUTRAL', 'ALL_ROLES']
