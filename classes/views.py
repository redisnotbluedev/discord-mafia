"""Discord UI views for the Mafia game.

This module contains all discord.py View, Button, and Select subclasses
used for player interaction.

Classes are organized by function:
- **Lobby views**: ConfirmView, StartGameView, JoinGameView
- **Settings views**: SettingsView, EnabledRolesSelect, ModelSelect,
  MafiaUp, MafiaDisplay, TownUp, TownDisplay, NeutralDisplay, DefaultButton
- **In-game views**: VoteView, VoteSelect, SelectView,
  SpecialActionsView, SpecialActionButton
"""

import discord, time, logging, data, asyncio, json
from collections import defaultdict
from typing import TYPE_CHECKING, Callable
from classes.roles import Role, Alignment, ALL_ROLES
from classes.player import Player, create_ai_players, AIAbstraction

if TYPE_CHECKING:
	from classes.abstractor import GameAbstractor
	from classes.scheduler import MafiaSheduler

logger = logging.getLogger(__name__)

ABSTAIN_LABEL = "Abstain"

class ConfirmView(discord.ui.View):
	"""A simple Yes/No confirmation dialog.

	Args:
		yes: Async callback invoked when Yes is clicked.
		no: Async callback invoked when No is clicked.
	"""

	def __init__(self, yes, no):
		self.yes = yes
		self.no = no
		super().__init__(timeout=300)

	@discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
	async def on_yes(self, interaction: discord.Interaction, _):
		await self.yes(interaction)

	@discord.ui.button(label="No", style=discord.ButtonStyle.red)
	async def on_no(self, interaction: discord.Interaction, _):
		await self.no(interaction)

class StartGameView(discord.ui.View):
	"""Initial lobby view with a single 'Play' button.

	When a player clicks Play, this view registers them as the game owner,
	loads AI models from models.json, creates AI players, and transitions
	to JoinGameView (the lobby with Join/Leave, Start, and Settings).
	"""

	def __init__(self, abstractor):
		self.abstractor: "GameAbstractor" = abstractor
		super().__init__(timeout=None)

	@discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
	async def start_game(self, interaction: discord.Interaction, _):
		if self.abstractor.running:
			return

		self.abstractor.players[interaction.user.id] = Player(interaction.user)
		try:
			with open("models.json") as f:
				m_data = json.load(f)
				models = [m["model"] for m in m_data.get("models", [])[:10]]
		except Exception:
			models = []

		for ai_player in create_ai_players(models):
			self.abstractor.players[hash(ai_player.name)] = ai_player

		self.abstractor.interactions[interaction.user.id] = interaction
		self.abstractor.running = True
		data.update_game_status(self.abstractor.bot)
		self.abstractor.last_lobby_id = None
		self.abstractor.owner = interaction.user
		self.abstractor.save_config()

		# discord.py doesn't say if this expires so just to make sure...
		message = await self.abstractor.bot.get_channel(interaction.message.channel.id).fetch_message(interaction.message.id)
		view = JoinGameView(self.abstractor, message, time.time() + 60 * 5)
		embed = view.generate_embed()

		await interaction.response.edit_message(embed=embed, view=view)

class JoinGameView(discord.ui.View):
	"""Lobby waiting room with Join/Leave, Start Game, and Settings buttons.

	Created when a player clicks Play in StartGameView.  Displays the player
	list, a countdown timer, and buttons for interaction.  The game owner
	can start immediately or wait for the timer.

	This view creates a MafiaScheduler instance which manages the actual
	game launch via a scheduled job.
	"""

	def __init__(self, abstractor, message, start_at):
		from classes.scheduler import MafiaSheduler

		self.abstractor: "GameAbstractor" = abstractor
		self.start_at = int(start_at)
		self.game: "MafiaSheduler" = MafiaSheduler(self.abstractor)
		self.game.message = message
		self.game.lobby = self
		self.running = False
		self.game.schedule(start_at)
		super().__init__(timeout=1000)

	def generate_embed(self, show_starting_soon=True):
		"""Build the lobby embed showing the player list and countdown.

		Also deduplicates player display names: if two players share the
		same base name, appends " (1)", " (2)", etc.

		Args:
			show_starting_soon: If True, includes the countdown field.

		Returns:
			A discord.Embed ready to send or edit into the lobby message.
		"""
		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)

		if show_starting_soon: embed.add_field(name="Starting soon", value=f"Game starting <t:{self.start_at}:R>\nNeed at least ({len(self.abstractor.players)}/5) players to start", inline=False)

		# Ensure unique names across all players
		counts = {}
		for player in self.abstractor.players.values():
			base_name = player.user.name.split(" #")[0]
			if base_name not in counts:
				counts[base_name] = 0
				player.name = base_name
			else:
				counts[base_name] += 1
				player.name = f"{base_name} ({counts[base_name]})"

		player_list = []
		for player in self.abstractor.players.values():
			result = "- "
			user = player.user

			if isinstance(user, discord.Member) and user == self.abstractor.owner: result += "<:owner:1474651989798289488> "
			result += player.name

			player_list.append(result)

		embed.add_field(name="Players", value="\n".join(player_list) if player_list else "No players yet!")

		return embed

	@discord.ui.button(label="Join/Leave", style=discord.ButtonStyle.blurple)
	async def join_game(self, interaction: discord.Interaction, _):
		"""Handles Join/Leave button clicks.

		If the game is already running, sends an error message.
		If the user is already a player, prompts for confirmation to leave.
		If the user is not a player, adds them to the game.
		If the user is the game owner and leaves, cancels the game.
		"""
		if self.running or (self.abstractor.game and self.abstractor.game.running):
			await interaction.response.send_message("The game's already running!", ephemeral=True)
			return
		if interaction.user.id in self.abstractor.players:
			async def yes(i: discord.Interaction):
				await i.response.edit_message(content="You left the game.", view=None)
				del self.abstractor.players[interaction.user.id]

				if interaction.user == self.abstractor.owner:
					await interaction.message.delete()
					self.game.start_job.cancel()
					self.abstractor.running = False
					data.update_game_status(self.abstractor.bot)
					await self.abstractor.on_message(True)
				else:
					embed = self.generate_embed()
					await interaction.message.edit(embed=embed)

			async def no(i: discord.Interaction):
				await i.response.edit_message(content="You canceled this action.", view=None)

			await interaction.response.send_message(
				"\n".join([
					"Are you sure you want to leave the game?",
					"You can always re-join after." if interaction.user != self.abstractor.owner else "This will end the game."
				]),
				view=ConfirmView(yes, no),
				ephemeral=True
			)
		else:
			self.abstractor.interactions[interaction.user.id] = interaction
			self.abstractor.players[interaction.user.id] = Player(interaction.user)
			embed = self.generate_embed()
			await interaction.response.edit_message(embed=embed)

	@discord.ui.button(label="Start Game", style=discord.ButtonStyle.green)
	async def start(self, interaction: discord.Interaction, _):
		"""Handles Start Game button clicks.

		If the game is already running, sends an error message.
		If the user is not the game owner, sends an error message.
		If the user is the game owner, starts the game.
		"""
		if self.running or (self.abstractor.game and self.abstractor.game.running):
			await interaction.response.send_message("The game's already running!", ephemeral=True)
			return
		if interaction.user == self.abstractor.owner:
			self.game.start_job.cancel()
			self.game.schedule(time.time())
			await interaction.response.edit_message()
		else:
			await interaction.response.send_message("You need to be the owner of this game to start it.", ephemeral=True)

	@discord.ui.button(emoji=discord.PartialEmoji(name="settings", id=1457586025105850470), style=discord.ButtonStyle.gray)
	async def settings(self, interaction: discord.Interaction, _):
		"""Handles Settings button clicks.

		If the user is not the game owner, sends an error message.
		If the user is the game owner, opens the settings menu.
		"""
		if interaction.user != self.abstractor.owner:
			await interaction.response.send_message("You need to be the owner of this game to change the settings.", ephemeral=True)
			return

		view = SettingsView(self.game)
		await view.render()

		commands = await self.abstractor.bot.tree.fetch_commands()
		get_command = lambda name: discord.utils.get(commands, name=name).mention

		await interaction.response.send_message(
			embed=discord.Embed(title="Settings", description="Change the configuration of this game.").add_field(name="Extra Commands", value=f"""
- {get_command("kick")}: Kick a player from the game.
- {get_command("llama10")}: Remove all AIs and add 10 Llamas.
				"""),
			view=view,
			ephemeral=True
		)
		view.message = await interaction.original_response()

class SettingsView(discord.ui.View):
	"""Ephemeral settings panel for game configuration.

	Displays controls for:
	- Mafia/Town count adjustment (MafiaUp, TownUp buttons + display buttons)
	- Enabled special roles (EnabledRolesSelect multi-select)
	- Active AI models (ModelSelect multi-select)
	- Reset to defaults (DefaultButton)
	"""

	def __init__(self, game):
		self.game = game
		self.config = game.config
		self.message = None
		super().__init__(timeout=None)

		# Add mafia and town controls
		self.add_item(DefaultButton())
		self.add_item(MafiaUp())
		self.add_item(MafiaDisplay())
		self.add_item(TownUp())
		self.add_item(TownDisplay())

		self.add_item(EnabledRolesSelect())
		self.add_item(ModelSelect())

		# Initialize models if not set
		if "models" not in self.config:
			try:
				with open("models.json") as f:
					m_data = json.load(f)
					self.config["models"] = [m["model"] for m in m_data.get("models", [])[:10]]
			except Exception:
				self.config["models"] = []

		# Initialize role configs (exclude Town and Mafia)
		for role in ALL_ROLES:
			if role.name not in ["Town", "Mafia"]:
				enabled = self.config.get(f"role_{role.name}", role.name in ["Doctor", "Sheriff"])  # Default Doctor and Sheriff enabled
				self.config[f"role_{role.name}"] = enabled

	async def render(self, interaction: discord.Interaction=None):
		"""Recalculate all settings UI state and update the message.

		Ensures town + mafia = total players, enforces mafia <= town,
		rebuilds the emoji bars, syncs select menu defaults, and edits
		the settings message.

		Args:
			interaction: If provided, responds to this interaction.
				Otherwise, edits the stored self.message directly.
		"""
		def get(id):
			return discord.utils.get(self.children, custom_id=id)

		total_players = len(self.game.abstractor.players)

		# Auto-adjust if total players changed
		current_mafia = self.config.get("mafia", 0)
		current_town = self.config.get("town", 0)
		if current_mafia + current_town > total_players:
			# Keep mafia, adjust town down
			self.config["town"] = max(1, total_players - current_mafia)
		elif current_mafia + current_town < total_players:
			# Add to town
			self.config["town"] = current_town + (total_players - (current_mafia + current_town))

		# Smart distribution: Mafia = ~1/3 of players, but keep Town > Mafia
		mafia = max(1, min(total_players // 3, total_players - 3))
		town = max(mafia + 1, total_players - mafia)

		mafia = self.config["mafia"]
		town = self.config["town"]

		# Ensure mafia <= town
		if mafia > town:
			mafia = town
			self.config["mafia"] = mafia

		# Mafia bar - show enabled special mafia roles
		enabled_special_mafia = [role for role in ALL_ROLES if self.config.get(f"role_{role.name}", False) and role.alignment == Alignment.MAFIA and role.is_special()]
		mafia_regular = max(mafia - len(enabled_special_mafia), 0)
		mafia_bar = "🔪" * mafia_regular + "".join(role.get_button_info()["emoji"] for role in enabled_special_mafia)
		get("mafia_display").label = f"{mafia_bar} ({mafia})"
		get("mafia_up").disabled = mafia >= town

		# Town bar - show enabled special town roles
		enabled_special_town = [role for role in ALL_ROLES if self.config.get(f"role_{role.name}", False) and role.alignment == Alignment.TOWN and role.is_special()]
		town_regular = max(town - len(enabled_special_town), 0)
		town_bar = "🏡" * town_regular + "".join(role.get_button_info()["emoji"] for role in enabled_special_town)
		get("town_display").label = f"{town_bar} ({town})"
		get("town_up").disabled = town >= total_players - 1

		# Neutral bar - show enabled neutral roles
		enabled_neutral = [role for role in ALL_ROLES if self.config.get(f"role_{role.name}", False) and role.alignment == Alignment.NEUTRAL]
		neutral_bar = "".join(role.get_button_info()["emoji"] for role in enabled_neutral)
		neutral_display = discord.utils.get(self.children, custom_id="neutral_display")
		if enabled_neutral:
			if not neutral_display:
				nd = NeutralDisplay()
				self.add_item(nd)
				neutral_display = nd
			neutral_display.label = f"Neutral: {neutral_bar} ({len(enabled_neutral)})"
		else:
			if neutral_display:
				self.children.remove(neutral_display)

		# Update select defaults
		select = get("enabled_roles")
		if select and isinstance(select, discord.ui.Select):
			for option in select.options:
				option.default = self.config.get(f"role_{option.value}", False)

		# Update model select defaults
		model_select = get("selected_models")
		if model_select and isinstance(model_select, discord.ui.Select):
			selected_models = self.config.get("models", [])
			for option in model_select.options:
				option.default = option.value in selected_models

		if interaction:
			await interaction.response.edit_message(view=self)
		elif self.message:
			await self.message.edit(view=self)

		# Update the lobby message if it exists to reflect changes in player list or settings
		if self.game.lobby and self.game.message:
			try:
				embed = self.game.lobby.generate_embed()
				await self.game.message.edit(embed=embed)
			except Exception:
				logger.exception("Failed to update lobby message")

class EnabledRolesSelect(discord.ui.Select):
	"""Multi-select dropdown for toggling special roles (Doctor, Sheriff, etc.)."""

	def __init__(self):
		options = []
		for role in ALL_ROLES:
			if role.name not in ["Town", "Mafia"]:
				options.append(discord.SelectOption(
					label=role.name,
					description=role.short_description,
					emoji=role.get_button_info()["emoji"],
					value=role.name
				))
		super().__init__(
			placeholder="Enabled Roles",
			min_values=0,
			max_values=len(options),
			options=options,
			custom_id="enabled_roles",
			row=3
		)

	async def callback(self, interaction: discord.Interaction):
		"""Handle role selection changes.

		Updates the config and re-renders the settings view.
		"""
		view: SettingsView = self.view  # type: ignore
		selected = set(self.values)
		for role in ALL_ROLES:
			if role.name not in ["Town", "Mafia"]:
				view.config[f"role_{role.name}"] = role.name in selected
		await view.render(interaction)

class ModelSelect(discord.ui.Select):
	"""Multi-select dropdown for choosing which AI models participate.

	Populated from models.json.  When the selection changes, AI players
	in the lobby are synced to match.
	"""

	def __init__(self):
		try:
			with open("models.json") as f:
				m_data = json.load(f)
				models = m_data.get("models", [])[:25]
		except Exception:
			models = []

		options = []
		for m in models:
			emoji = m.get("emoji")

			if emoji:
				parts = emoji.split(":")
				emoji = discord.PartialEmoji(
					name=parts[1],
					animated="a" in parts[0],
					id=parts[2].rstrip(">")
				)

			options.append(discord.SelectOption(
				label=m["name"],
				value=m["model"],
				emoji=emoji
			))

		super().__init__(
			placeholder="AI Models",
			min_values=0,
			max_values=len(options) if options else 1,
			options=options,
			custom_id="selected_models",
			row=4
		)

	async def callback(self, interaction: discord.Interaction):
		"""Handle model selection changes.

		Updates the player list and re-renders the settings view.
		"""
		view: SettingsView = self.view  # type: ignore
		view.config["models"] = self.values

		# Sync AI players in the lobby
		humans = {k: v for k, v in view.game.abstractor.players.items() if not isinstance(v.user, AIAbstraction)}
		view.game.abstractor.players.clear()
		view.game.abstractor.players.update(humans)
		for ai_player in create_ai_players(view.config["models"]):
			view.game.abstractor.players[hash(ai_player.name)] = ai_player

		await view.render(interaction)

class MafiaUp(discord.ui.Button):
	"""Button to increment the mafia player count by one."""

	def __init__(self):
		super().__init__(label="+", style=discord.ButtonStyle.green, custom_id="mafia_up", row=1)

	async def callback(self, interaction: discord.Interaction):
		view: SettingsView = self.view  # type: ignore
		total_players = len(view.game.abstractor.players)
		new_mafia = view.config["mafia"] + 1
		if new_mafia <= view.config["town"]:
			view.config["mafia"] = min(new_mafia, total_players - 3)
		await view.render(interaction)

class MafiaDisplay(discord.ui.Button):
	"""Disabled display button showing the mafia emoji bar and count."""

	def __init__(self):
		super().__init__(label="🔪 (1)", style=discord.ButtonStyle.gray, custom_id="mafia_display", disabled=True, row=1)

class TownUp(discord.ui.Button):
	"""Button to increment the town player count by one."""

	def __init__(self):
		super().__init__(label="+", style=discord.ButtonStyle.green, custom_id="town_up", row=2)

	async def callback(self, interaction: discord.Interaction):
		view: SettingsView = self.view  # type: ignore
		total_players = len(view.game.abstractor.players)
		new_town = view.config["town"] + 1
		view.config["town"] = min(new_town, total_players - 1)
		if view.config["mafia"] > view.config["town"]:
			view.config["mafia"] = view.config["town"]
		# If town + mafia exceeds total, auto-decrement mafia
		if view.config["town"] + view.config["mafia"] > total_players:
			view.config["mafia"] = max(1, total_players - view.config["town"])
		await view.render(interaction)

class TownDisplay(discord.ui.Button):
	"""Disabled display button showing the town emoji bar and count."""

	def __init__(self):
		super().__init__(label="🏡 (1)", style=discord.ButtonStyle.gray, custom_id="town_display", disabled=True, row=2)

class NeutralDisplay(discord.ui.Button):
	"""Disabled display button for neutral roles (dynamically added/removed)."""

	def __init__(self):
		super().__init__(label="\u200b", style=discord.ButtonStyle.gray, custom_id="neutral_display", disabled=True, row=0)

class DefaultButton(discord.ui.Button):
	"""Button to reset all settings to their defaults.

	Resets role toggles (Doctor + Sheriff enabled), recalculates mafia/town
	split (~1/3 mafia), reloads all models from models.json, and syncs
	the lobby player list.
	"""

	def __init__(self):
		super().__init__(label="Default", style=discord.ButtonStyle.blurple, custom_id="default", row=0)

	async def callback(self, interaction: discord.Interaction):
		"""Handle default settings reset.

		Resets role toggles, counts, and models, then re-renders the view.
		"""
		view: SettingsView = self.view  # type: ignore
		total_players = len(view.game.abstractor.players)

		# Reset role toggles to defaults
		for role in ALL_ROLES:
			if role.name not in ["Town", "Mafia"]:
				enabled = role.name in ["Doctor", "Sheriff"]
				view.config[f"role_{role.name}"] = enabled
		# Town and Mafia are always enabled
		view.config["role_Town"] = True
		view.config["role_Mafia"] = True

		# Reset counts to smart defaults
		mafia = max(1, min(total_players // 3, total_players - 3))
		town = max(mafia + 1, total_players - mafia)
		view.config["mafia"] = mafia
		view.config["town"] = town

		# Reset models to defaults (all 10)
		try:
			with open("models.json") as f:
				m_data = json.load(f)
				view.config["models"] = [m["model"] for m in m_data.get("models", [])[:10]]
		except Exception:
			pass

		# Sync AI players in the lobby
		humans = {k: v for k, v in view.game.abstractor.players.items() if not isinstance(v.user, AIAbstraction)}
		view.game.abstractor.players.clear()
		view.game.abstractor.players.update(humans)
		for ai_player in create_ai_players(view.config["models"]):
			view.game.abstractor.players[hash(ai_player.name)] = ai_player

		await view.render(interaction)

class VoteSelect(discord.ui.Select):
	"""Select menu for human players to cast a vote.

	Each interaction records the vote in VoteView.votes, reformats the
	tally, and updates the poll message.  Disables the select when all
	human votes are in.
	"""

	def __init__(self, players, placeholder, emoji, allow_abstain: bool = False):
		"""Initialize a VoteSelect.

		Args:
			players: List of player names to vote for.
			placeholder: Placeholder text for the select menu.
			emoji: Emoji to use for the select options. All of them get the
			  same emoji.
			allow_abstain: Whether to allow players to abstain from voting.
		"""
		options = [
			discord.SelectOption(label=player, emoji=emoji)
			for player in players
		]

		if allow_abstain:
			options.append(discord.SelectOption(label=ABSTAIN_LABEL, emoji="⏭️"))

		super().__init__(
			placeholder=placeholder,
			min_values=1,
			max_values=1,
			options=options
		)

	async def callback(self, interaction: discord.Interaction):
		"""Handle vote selection.

		Records the vote, updates the tally, and re-renders the view.
		"""
		view: VoteView = self.view  # type: ignore

		if interaction.user.id not in view.allowed_voters:
			await interaction.response.send_message("You're not a participant in this game.", ephemeral=True)
			return

		selection = self.values[0]
		view.votes[interaction.user.id] = selection

		vote_details = defaultdict(list)
		for vid, choice in view.votes.items():
			voter_name = view.voter_names.get(vid, "Unknown")
			vote_details[choice].append(voter_name)

		lines = []
		for name in view.player_names:
			voters = vote_details.get(name, [])
			if voters:
				lines.append(f"- {name}: {', '.join(sorted(voters))} ({len(voters)})")

		if view.allow_abstain and ABSTAIN_LABEL in vote_details:
			voters = vote_details[ABSTAIN_LABEL]
			lines.append(f"- {ABSTAIN_LABEL}: {', '.join(sorted(voters))} ({len(voters)})")

		if not lines:
			lines = ["No votes yet."]

		content = view.base_message + "\n" + "\n\n**Votes:**\n" + "\n".join(lines)

		if sum(1 for uid in view.votes.keys() if uid in view.allowed_voters) >= view.required_votes:
			self.disabled = True

		await interaction.response.edit_message(content=content, view=view)

class VoteView(discord.ui.View):
	"""View containing a VoteSelect for human voting.

	Created by TurnManager.run_vote().  Holds shared state between the
	UI select and the voting manager:
		votes: dict of voter_id -> chosen_name (shared with run_vote).
		allowed_voters: set of Discord user IDs who may vote.
		required_votes: how many human votes to wait for.
		base_message: the message text above the tally.
	"""

	def __init__(self, players: list[str], placeholder="Vote on a player.", emoji="🗳️", allow_abstain: bool = False, voter_names: dict[int, str] = None):
		super().__init__(timeout=None)
		self.allow_abstain = allow_abstain
		self.add_item(VoteSelect(players, placeholder, emoji, allow_abstain=allow_abstain))
		self.votes: dict[int, str] = {}
		self.allowed_voters: set[int] = set()
		self.required_votes: int = 0
		self.base_message: str = ""
		self.player_names: list[str] = players
		self.voter_names = voter_names or {}

class SelectView(discord.ui.View):
	"""Generic single-select view used by role night actions.

	Args:
		candidates: List of SelectOption items to choose from.
		callback: Async function called when a selection is made.
	"""

	def __init__(self, candidates: list, callback: Callable):
		super().__init__(timeout=None)
		self.dropdown = discord.ui.Select(options=candidates)
		self.dropdown.callback = callback
		self.add_item(self.dropdown)

class SpecialActionsView(discord.ui.View):
	"""Night actions panel showing one button per special role.

	Displayed during the night phase.  Each alive player with a special
	role sees a button for their action (e.g. Doctor: Save, Sheriff:
	Investigate).  Tracks which humans have acted and enforces a 3-minute
	timeout; unacted players receive a failure penalty.

	Attributes:
		acted_players: Set of user IDs who have completed their action.
		pending_humans: Set of user IDs still expected to act.
	"""

	def __init__(self, alive_players: list[Player]):
		super().__init__(timeout=None)
		self.players = alive_players
		self.turn_manager = None  # Will be set by game.py for broadcasting
		self.game = None  # Will be set by game.py
		self.acted_players = set()
		self.pending_humans = set()

		added_roles = set()
		for player in alive_players:
			if player.role.is_special() and player.role.name not in added_roles:
				self.add_item(SpecialActionButton(player.role))
				added_roles.add(player.role.name)

		self.pending_humans = {p.user.id for p in alive_players if p.role.is_special() and isinstance(p.user, discord.Member) and p.role.can_act(p)}

	def get(self, id):
		return discord.utils.get(self.children, custom_id=id)

	async def wait_for_humans(self):
		"""Block until all pending humans have acted or the 3-minute timeout.

		Players who don't act in time receive a failure penalty via
		handle_player_failure.  Players who do act get their failure
		counter reset to 0.
		"""
		start_time = asyncio.get_event_loop().time()
		timeout = 180.0  # 3 minutes
		while self.pending_humans:
			if (asyncio.get_event_loop().time() - start_time) >= timeout:
				# Handle timeout for players who didn't act
				if self.game and self.game.turns:
					for pid in list(self.pending_humans):
						player = next((p for p in self.players if p.user.id == pid), None)
						if player:
							await self.game.turns.handle_player_failure(player)
				self.pending_humans.clear()
				return
			await asyncio.sleep(1)

		# Reset failures for those who did act
		if self.game and self.game.turns:
			for pid in self.acted_players:
				player = next((p for p in self.players if p.user.id == pid), None)
				if player:
					self.game.turns.player_failures[player.user] = 0

	async def handle_ai_special_action(self, player: Player):
		"""Delegate an AI player's night action to their role's AI handler.

		Calls player.role.night_action_ai(), which uses the TurnManager
		to get an LLM completion and apply the result (e.g. kill, save,
		investigate).  Errors are logged but do not propagate.
		"""
		if not self.game:
			return

		try:
			await player.role.night_action_ai(self.game, player)
		except Exception as e:
			model = getattr(player.user, "model", None)
			if model:
				logger.exception("Error getting AI %s action (model=%s): %s", player.role.name, model, e)
			else:
				logger.exception("Error getting AI %s action: %s", player.role.name, e)

class SpecialActionButton(discord.ui.Button):
	"""A night action button for a specific role (e.g. 'Save', 'Investigate').

	Limits interaction to players who actually hold a relevant role. 
	Delegates to role.handle_button_click() for the actual action and UI.
	Checks that the player is not listed as having already acted, but does not
	set this state itself.
	"""

	def __init__(self, role: Role):
		button_info = role.get_button_info()
		super().__init__(
			label=button_info["label"],
			style=discord.ButtonStyle.blurple,
			emoji=button_info["emoji"],
			custom_id=f"action_{role.name}"
		)
		self.role = role

	async def callback(self, interaction: discord.Interaction):
		"""Route clicks to the interacting player's role."""
		view: SpecialActionsView = self.view  # type: ignore
		if interaction.user.id not in [p.user.id for p in view.players if p.role == self.role]:
			await interaction.response.send_message("Not for you.", ephemeral=True)
			return
		elif interaction.user.id in view.acted_players:
			await interaction.response.send_message("You already performed your action!", ephemeral=True)
			return

		player = next(p for p in view.players if p.user.id == interaction.user.id and p.role == self.role)
		await self.role.handle_button_click(view.game, player, interaction, action_view=view)
