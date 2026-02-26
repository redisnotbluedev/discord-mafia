from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from classes.player import Player

class Alignment(Enum):
	TOWN = "Town"
	MAFIA = "Mafia"
	NEUTRAL = "Neutral"

NEUTRAL = Alignment.NEUTRAL

class Role:
	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str, emoji: str = "❓"):
		self.name = name
		self.alignment = alignment
		self.description = description
		self.short_description = short_description
		self.emoji = emoji

	def __str__(self):
		return self.name

	def __eq__(self, other):
		if isinstance(other, Role):
			return self.name == other.name
		return False

	def __hash__(self):
		return hash(self.name)

	def describe(self):
		return self.description

	def is_special(self):
		return False

	def night_action_type(self):
		return None

	def get_button_info(self):
		return {"label": self.name, "emoji": self.emoji}

	def get_prompt(self):
		return f"## {self.name}\nWhat do you want to do?"

	async def handle_button_click(self, game, player, interaction):
		pass

	async def on_night_end(self, game, player):
		pass

	async def night_action_ai(self, game, player):
		pass

	def can_act(self, player) -> bool:
		return True

	def win_condition(self, player, players):
		# Default: no win condition
		return False

class SelectRole(Role):
	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str, emoji: str, action_label: str, skippable: bool = False):
		super().__init__(name, alignment, description, short_description)
		self.emoji = emoji
		self.action_label = action_label
		self.skippable = skippable

	def is_special(self):
		return True

	def get_button_info(self):
		return {"label": self.name, "emoji": self.emoji}

	def get_prompt(self):
		return f"## {self.name}\nWho do you want to {self.action_label}?"

	def get_options(self, game, player):
		return [p for p in game.get_alive_players() if p.alive]

	async def handle_button_click(self, game, player, interaction):
		import discord
		from classes.views import SelectView
		options = self.get_options(game, player)
		select_options = [
			discord.SelectOption(label=p.name, value=str(i), emoji=self.emoji)
			for i, p in enumerate(options)
		]
		
		if self.skippable:
			select_options.append(discord.SelectOption(label="Abstain", value="abstain", emoji="⏭️"))

		select_view = SelectView(select_options, lambda inter: self.on_selected(game, player, inter, options))
		await interaction.response.send_message(self.get_prompt(), view=select_view, ephemeral=True)

	async def on_selected(self, game, player, interaction, options):
		selection = interaction.data['values'][0]
		if selection == "abstain":
			await interaction.response.edit_message(content=f"You chose to abstain.", view=None)
			return

		user = options[int(selection)]
		await self.handle_selection(game, player, user)
		await interaction.response.edit_message(content=f"You chose to {self.action_label} {user.name}.", view=None)

	async def handle_selection(self, game, player, user):
		pass

	async def night_action_ai(self, game, player):
		options = self.get_options(game, player)
		opt_names = [p.name for p in options]
		prompt_options = opt_names.copy()
		if self.skippable:
			prompt_options.append("abstain")

		prompt = f"NIGHT: {self.name.upper()} {self.action_label.upper()}\n> {self.get_prompt()}\n"
		if self.skippable:
			prompt += "Note: You are NOT required to act. If you don't have a strong suspicion, you should 'abstain' to avoid hurting your team.\n"
		prompt += "Available options:\n" + "\n".join([f"- {name}" for name in prompt_options])
		
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
	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str):
		super().__init__(name, alignment, description, short_description, "🧑‍⚕️", "save", skippable=False)

	def night_action_type(self):
		return "save"

	async def handle_selection(self, game, player, user):
		saves = game.night_actions.setdefault("saves", [])
		old_save = player.role_state.get("pending_save")
		if old_save and old_save in saves:
			saves.remove(old_save)
		
		saves.append(user)
		player.role_state["pending_save"] = user

	async def on_night_end(self, game, player):
		player.role_state["last_saved"] = player.role_state.get("pending_save")
		player.role_state["pending_save"] = None

class KillRole(SelectRole):
	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str, skippable: bool = False):
		super().__init__(name, alignment, description, short_description, "🔫", "kill", skippable=skippable)

	def night_action_type(self):
		return "kill"

	async def handle_selection(self, game, player, user):
		game.night_actions.setdefault("kills", []).append(user)

class InvestigateRole(SelectRole):
	def __init__(self, name: str, alignment: Alignment, description: str, short_description: str):
		super().__init__(name, alignment, description, short_description, "🕵️", "investigate", skippable=False)

	def night_action_type(self):
		return "investigate"

	def get_options(self, game, player):
		return [p for p in game.get_alive_players() if p.alive and p != player]

	async def on_selected(self, game, player, interaction, options):
		selection = interaction.data['values'][0]
		user = options[int(selection)]
		await self.handle_selection(game, player, user)
		await interaction.response.edit_message(content=f"You chose to investigate {user.name}. {user.name} is **{user.role.alignment.value.upper()}**!", view=None)

	async def handle_selection(self, game, player, user):
		result_prompt = f"{user.name} is **{user.role.alignment.value.upper()}**."
		from classes.player import AIAbstraction
		if isinstance(player.user, AIAbstraction):
			await game.turns.create_ai_completion(player, result_prompt)
# Import all roles
from .townsperson import Town, TOWN
from .mafia import Mafia, MAFIA
from .doctor import Doctor, DOCTOR
from .sheriff import Sheriff, SHERIFF
from .vigilante import Vigilante, VIGILANTE
from .jester import Jester, JESTER

# List of all roles
ALL_ROLES = [TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE, JESTER]

__all__ = ['Alignment', 'Role', 'SaveRole', 'KillRole', 'InvestigateRole', 'Town', 'Mafia', 'Doctor', 'Sheriff', 'Vigilante', 'Jester', 'TOWN', 'MAFIA', 'DOCTOR', 'SHERIFF', 'VIGILANTE', 'JESTER', 'NEUTRAL', 'ALL_ROLES']

# Example of adding a new role:
# Create a new file in this directory, e.g., newrole.py
# from classes.roles import SaveRole, Alignment  # Or KillRole, InvestigateRole
#
# class NewRole(SaveRole):  # Inherit from appropriate base class
#     def __init__(self):
#         super().__init__("NewRole", Alignment.TOWN, "Description of the new role.", "Short description.")
#
#     # Override methods as needed for custom behavior
#     async def handle_button_click(self, game, player, interaction):
#         # Custom button logic if needed
#         await super().handle_button_click(game, player, interaction)
#
#     async def night_action_ai(self, game, player):
#         # Custom AI logic
#         await super().night_action_ai(game, player)
#
# NEW_ROLE = NewRole()
# Then, in __init__.py:
# from .newrole import NewRole, NEW_ROLE
# ALL_ROLES.append(NEW_ROLE)
# __all__.extend(['NewRole', 'NEW_ROLE'])
