import discord, time, logging, data
from collections import defaultdict
from typing import TYPE_CHECKING, Callable
from classes.roles import Role, Alignment, ALL_ROLES
from classes.player import Player, create_ai_players

if TYPE_CHECKING:
	from classes.abstractor import GameAbstractor
	from classes.scheduler import MafiaSheduler

logger = logging.getLogger(__name__)

ABSTAIN_LABEL = "Abstain"

class ConfirmView(discord.ui.View):
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
	def __init__(self, abstractor):
		self.abstractor: "GameAbstractor" = abstractor
		super().__init__(timeout=None)

	@discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
	async def start_game(self, interaction: discord.Interaction, _):
		if self.abstractor.running:
			return

		self.abstractor.players[interaction.user.id] = Player(interaction.user)
		for ai_player in create_ai_players():
			# Use hash of AI name as key since AIAbstraction doesn't have an id
			self.abstractor.players[hash(ai_player.name)] = ai_player

		self.abstractor.interactions[interaction.user.id] = interaction
		self.abstractor.running = True
		self.abstractor.last_lobby_id = None
		self.abstractor.owner = interaction.user
		self.abstractor.save_config()

		view = JoinGameView(self.abstractor, interaction.message, time.time() + 60 * 5)
		embed = view.generate_embed()
		view.game.lobby = view

		await interaction.response.edit_message(embed=embed, view=view)

class JoinGameView(discord.ui.View):
	def __init__(self, abstractor, message, start_at):
		from classes.scheduler import MafiaSheduler

		self.abstractor: "GameAbstractor" = abstractor
		self.start_at = int(start_at)
		self.game: "MafiaSheduler" = MafiaSheduler(self.abstractor)
		self.game.message = message
		self.running = False
		self.game.schedule(start_at)
		super().__init__(timeout=1000)

	def generate_embed(self):
		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)

		embed.add_field(name="Starting soon", value=f"Game starting <t:{self.start_at}:R>\nNeed at least ({len(self.abstractor.players)}/5) players to start", inline=False)
		player_list = []
		for player in self.abstractor.players.values():
			result = "- "
			user = player.user

			if isinstance(user, discord.Member):
				if user == self.abstractor.owner: result += "<:owner:1457538443327311872> "
				result += user.display_name or user.name
			else:
				result += user.name

			player_list.append(result)

		embed.add_field(name="Players", value="\n".join(player_list) if player_list else "No players yet!")

		return embed

	@discord.ui.button(label="Join/Leave", style=discord.ButtonStyle.blurple)
	async def join_game(self, interaction: discord.Interaction, _):
		if self.running or (self.abstractor.game and self.abstractor.game.running):
			await interaction.response.send_message("The game's already running!", ephemeral=True)
			return
		if interaction.user.id in self.abstractor.players:
			async def yes(i: discord.Interaction):
				await i.response.edit_message(content="You left the game.", view=None)
				del self.abstractor.players[interaction.user.id]

				if interaction.user == self.abstractor.owner:
					await interaction.message.edit(
						embed=discord.Embed(
							title="AI Plays Mafia",
							description="The series by Turing Games, now as a Discord bot!",
							color=discord.Color.blurple(),
						),
						view=StartGameView(self.abstractor)
					)
					self.game.start_job.cancel()
					self.abstractor.running = False
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
		if interaction.user != self.abstractor.owner:
			await interaction.response.send_message("You need to be the owner of this game to change the settings.", ephemeral=True)
			return

		view = SettingsView(self.game)
		await view.render()
		await interaction.response.send_message(
			embed=discord.Embed(title="Settings", description="Change the configuration of this game."),
			view=view,
			ephemeral=True
		)
		view.message = await interaction.original_response()

class SettingsView(discord.ui.View):
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

		# Initialize role configs (exclude Town and Mafia)
		for role in ALL_ROLES:
			if role.name not in ["Town", "Mafia"]:
				enabled = self.config.get(f"role_{role.name}", role.name in ["Doctor", "Sheriff"])  # Default Doctor and Sheriff enabled
				self.config[f"role_{role.name}"] = enabled

	async def render(self, interaction: discord.Interaction=None):
		def get(id):
			return discord.utils.get(self.children, custom_id=id)

		# Update enabled roles select with current selections
		enabled_select = get("enabled_roles")
		if enabled_select:
			enabled_roles = [role.name for role in ALL_ROLES if self.config.get(f"role_{role.name}", False) and role.name not in ["Town", "Mafia"]]
			new_options = []
			for opt in enabled_select.options:
				new_options.append(discord.SelectOption(
					label=opt.label,
					description=opt.description,
					emoji=opt.emoji,
					value=opt.value,
					default=opt.value in enabled_roles
				))
			enabled_select.options = new_options

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

		self.config.setdefault("mafia", mafia)
		self.config.setdefault("town", town)

		mafia = self.config["mafia"]
		town = self.config["town"]

		# Ensure mafia < town
		if mafia >= town:
			town = mafia + 1
			self.config["town"] = town

		# Mafia bar
		mafia_bar = "🔪" * mafia
		get("mafia_display").label = f"{mafia_bar} ({mafia})"
		get("mafia_up").disabled = mafia >= town - 1

		# Town bar - show enabled special town roles
		enabled_special_town = [role for role in ALL_ROLES if self.config.get(f"role_{role.name}", False) and role.alignment == Alignment.TOWN and role.is_special()]
		town_regular = max(town - len(enabled_special_town), 0)
		town_bar = "🏡" * town_regular + "".join(role.get_button_info()["emoji"] for role in enabled_special_town)
		get("town_display").label = f"{town_bar} ({town})"
		get("town_up").disabled = town >= total_players - 1

		if interaction:
			await interaction.response.edit_message(view=self)
		elif self.message:
			await self.message.edit(view=self)



class EnabledRolesSelect(discord.ui.Select):
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
		view: SettingsView = self.view  # type: ignore
		selected = set(self.values)
		for role in ALL_ROLES:
			if role.name not in ["Townsperson", "Mafia"]:
				view.config[f"role_{role.name}"] = role.name in selected
		await view.render(interaction)

class MafiaUp(discord.ui.Button):
	def __init__(self):
		super().__init__(label="+", style=discord.ButtonStyle.green, custom_id="mafia_up", row=1)

	async def callback(self, interaction: discord.Interaction):
		view: SettingsView = self.view  # type: ignore
		total_players = len(view.game.abstractor.players)
		new_mafia = view.config["mafia"] + 1
		if new_mafia >= view.config["town"]:
			view.config["town"] = new_mafia + 1
		view.config["mafia"] = min(new_mafia, total_players - 3)
		await view.render(interaction)

class MafiaDisplay(discord.ui.Button):
	def __init__(self):
		super().__init__(label="🔪 (1)", style=discord.ButtonStyle.gray, custom_id="mafia_display", disabled=True, row=1)

class TownUp(discord.ui.Button):
	def __init__(self):
		super().__init__(label="+", style=discord.ButtonStyle.green, custom_id="town_up", row=2)

	async def callback(self, interaction: discord.Interaction):
		view: SettingsView = self.view  # type: ignore
		total_players = len(view.game.abstractor.players)
		new_town = view.config["town"] + 1
		if new_town <= view.config["mafia"]:
			view.config["mafia"] = new_town - 1
		view.config["town"] = min(new_town, total_players - 1)
		# If town + mafia exceeds total, auto-decrement mafia
		if view.config["town"] + view.config["mafia"] > total_players:
			view.config["mafia"] = max(1, total_players - view.config["town"])
		await view.render(interaction)

class TownDisplay(discord.ui.Button):
	def __init__(self):
		super().__init__(label="🏡 (1)", style=discord.ButtonStyle.gray, custom_id="town_display", disabled=True, row=2)

class DefaultButton(discord.ui.Button):
	def __init__(self):
		super().__init__(label="Default", style=discord.ButtonStyle.blurple, custom_id="default", row=0)

	async def callback(self, interaction: discord.Interaction):
		view: SettingsView = self.view  # type: ignore
		total_players = len(view.game.abstractor.players)

		# Reset role toggles to defaults
		for role in ALL_ROLES:
			if role.name not in ["Townsperson", "Mafia"]:
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

		await view.render(interaction)

class VoteSelect(discord.ui.Select):
	def __init__(self, players, placeholder, emoji, allow_abstain: bool = False):
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
		view: VoteView = self.view  # type: ignore

		# Only participants can vote
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

		# If everyone has voted, disable the select
		if sum(1 for uid in view.votes.keys() if uid in view.allowed_voters) >= view.required_votes:
			self.disabled = True

		await interaction.response.edit_message(content=content, view=view)

class VoteView(discord.ui.View):
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
	def __init__(self, candidates: list, callback: Callable):
		super().__init__(timeout=None)
		self.dropdown = discord.ui.Select(options=candidates)
		self.dropdown.callback = callback
		self.add_item(self.dropdown)

class SpecialActionsView(discord.ui.View):
	def __init__(self, alive_players: list[Player]):
		super().__init__(timeout=None)
		self.players = alive_players
		self.turn_manager = None  # Will be set by game.py for broadcasting
		self.game = None  # Will be set by game.py
		self.acted_players = set()

		# Add buttons for special roles
		added_roles = set()
		for player in alive_players:
			if player.role.is_special() and player.role.name not in added_roles and player.role.can_act(player):
				self.add_item(SpecialActionButton(player.role))
				added_roles.add(player.role.name)

	def get(self, id):
		return discord.utils.get(self.children, custom_id=id)

	async def handle_ai_special_action(self, player: Player):
		"""Handle AI special action based on role."""
		if not self.game:
			return

		try:
			await player.role.night_action_ai(self.game, player)
		except Exception as e:
			logger.error(f"Error getting AI {player.role.name} action: {e}")

class SpecialActionButton(discord.ui.Button):
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
		view: SpecialActionsView = self.view  # type: ignore
		if interaction.user.id not in [p.user.id for p in view.players if p.role == self.role]:
			await interaction.response.send_message("Not for you.", ephemeral=True)
			return
		elif interaction.user.id in view.acted_players:
			await interaction.response.send_message("You already performed your action!", ephemeral=True)
			return

		player = next(p for p in view.players if p.user.id == interaction.user.id and p.role == self.role)
		await self.role.handle_button_click(view.game, player, interaction)
		view.acted_players.add(interaction.user.id)
