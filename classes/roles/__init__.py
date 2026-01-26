from enum import Enum

class Alignment(Enum):
	TOWN = "Town"
	MAFIA = "Mafia"
	NEUTRAL = "Neutral"

NEUTRAL = Alignment.NEUTRAL

class Role:
	def __init__(self, name: str, alignment: Alignment, description: str):
		self.name = name
		self.alignment = alignment
		self.description = description

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
		return {"label": self.name, "emoji": "❓"}

	def get_prompt(self):
		return f"## {self.name}\nWhat do you want to do?"

	async def handle_button_click(self, game, player, interaction):
		# Default, do nothing
		pass

	async def night_action_ai(self, game, player):
		# Default, do nothing
		pass

	def win_condition(self, player, players):
		# Default: no win condition
		return False

class SaveRole(Role):
	def night_action_type(self):
		return "save"

	def get_button_info(self):
		return {"label": self.name, "emoji": "🧑‍⚕️"}

	def get_prompt(self):
		return f"## {self.name}\nWho do you want to save?"

	async def handle_button_click(self, game, player, interaction):
		import discord
		from classes.views import SelectView
		select_view = SelectView([
			discord.SelectOption(label=p.name, value=str(i), emoji="💊")
			for i, p in enumerate(game.get_alive_players()) if p.alive
		], lambda inter: self.on_save_selected(game, player, inter))
		await interaction.response.send_message(self.get_prompt(), view=select_view, ephemeral=True)

	async def on_save_selected(self, game, player, interaction):
		index = int(interaction.values[0])
		user = game.get_alive_players()[index]
		await self.handle_save_selection(game, player, user)
		await interaction.response.edit_message(content=f"You chose to save {user.name}.", view=None)

	async def handle_save_selection(self, game, player, user):
		game.night_actions.setdefault("saves", []).append(user)
		player.role_state["last_saved"] = user

class KillRole(Role):
	def night_action_type(self):
		return "kill"

	def get_button_info(self):
		return {"label": self.name, "emoji": "🔫"}

	def get_prompt(self):
		return f"## {self.name}\nWho do you want to kill?"

	async def handle_button_click(self, game, player, interaction):
		import discord
		from classes.views import SelectView
		select_view = SelectView([
			discord.SelectOption(label=p.name, value=str(i), emoji="🔫")
			for i, p in enumerate(game.get_alive_players()) if p.alive
		], lambda inter: self.on_kill_selected(game, player, inter))
		await interaction.response.send_message(self.get_prompt(), view=select_view, ephemeral=True)

	async def on_kill_selected(self, game, player, interaction):
		index = int(interaction.values[0])
		user = game.get_alive_players()[index]
		await self.handle_kill_selection(game, player, user)
		await interaction.response.edit_message(content=f"You chose to kill {user.name}.", view=None)

	async def handle_kill_selection(self, game, player, user):
		game.night_actions.setdefault("kills", []).append(user)

class InvestigateRole(Role):
	def night_action_type(self):
		return "investigate"

	def get_button_info(self):
		return {"label": self.name, "emoji": "🕵️"}

	def get_prompt(self):
		return f"## {self.name}\nWho do you want to investigate?"

	async def handle_button_click(self, game, player, interaction):
		import discord
		from classes.views import SelectView
		select_view = SelectView([
			discord.SelectOption(label=p.name, value=str(i), emoji="🕵️")
			for i, p in enumerate(game.get_alive_players()) if p.alive and p != player
		], lambda inter: self.on_investigate_selected(game, player, inter))
		await interaction.response.send_message(self.get_prompt(), view=select_view, ephemeral=True)

	async def on_investigate_selected(self, game, player, interaction):
		index = int(interaction.values[0])
		user = game.get_alive_players()[index]
		await self.handle_investigate_selection(game, player, user)
		await interaction.response.edit_message(content=f"You chose to investigate {user.name}. {user.name} is **{user.role.alignment.value.upper()}**!", view=None)

	async def handle_investigate_selection(self, game, player, user):
		result_prompt = f"{user.name} is **{user.role.alignment.value.upper()}**."
		await game.turns.create_ai_completion(player, result_prompt)

# Import all roles
from .townsperson import Townsperson, TOWN
from .mafia import Mafia, MAFIA
from .doctor import Doctor, DOCTOR
from .sheriff import Sheriff, SHERIFF
from .vigilante import Vigilante, VIGILANTE
from .jester import Jester, JESTER

# Update base win conditions
TOWN.win_condition = lambda self, player, players: not any(p.alive and p.role.alignment == Alignment.MAFIA for p in players)
MAFIA.win_condition = lambda self, player, players: sum(1 for p in players if p.alive and p.role.alignment == Alignment.MAFIA) >= sum(1 for p in players if p.alive and p.role.alignment != Alignment.MAFIA)

# List of all roles
ALL_ROLES = [TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE, JESTER]

__all__ = ['Alignment', 'Role', 'SaveRole', 'KillRole', 'InvestigateRole', 'Townsperson', 'Mafia', 'Doctor', 'Sheriff', 'Vigilante', 'Jester', 'TOWN', 'MAFIA', 'DOCTOR', 'SHERIFF', 'VIGILANTE', 'JESTER', 'NEUTRAL', 'ALL_ROLES']

# Example of adding a new role:
# Create a new file in this directory, e.g., newrole.py
# from classes.roles import SaveRole, Alignment  # Or KillRole, InvestigateRole
#
# class NewRole(SaveRole):  # Inherit from appropriate base class
#     def __init__(self):
#         super().__init__("NewRole", Alignment.TOWN, "Description of the new role.")
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