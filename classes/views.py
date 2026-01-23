import discord, time, asyncio, logging
from typing import TYPE_CHECKING, Callable
from classes.player import Player, create_ai_players, Role

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
		if self.running or self.abstractor.game.running:
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
		self.message = None
		super().__init__(timeout=None)

	async def render(self, interaction: discord.Interaction=None):
		def get(id):
			return discord.utils.get(self.children, custom_id=id)

		total_players = len(self.game.abstractor.players)

		# Smart distribution: Mafia = ~1/3 of players, but keep Town >= 3
		mafia = max(1, min(total_players // 3, total_players - 3))
		town = total_players - mafia

		self.game.config.setdefault("mafia", mafia)
		self.game.config.setdefault("town", town)

		mafia = self.game.config["mafia"]
		town = self.game.config["town"]

		# Mafia bar
		mafia_bar = "🔪" * mafia
		get("mafia_display").label = f"{mafia_bar} ({mafia})"
		get("mafia_up").disabled = mafia >= total_players - 3

		# Town bar - show doctor and sheriff separately
		town_regular = max(town - 2, 0)  # Subtract doctor and sheriff
		town_bar = "🏡" * town_regular + "🧑‍⚕️" + "🤠"
		if town_regular < town - 2:
			# If town is < 2, adjust what roles exist
			if town == 1:
				town_bar = "🏡"
			elif town == 2:
				town_bar = "🏡🧑‍⚕️"
		get("town_display").label = f"{town_bar} ({town})"
		get("town_up").disabled = town >= total_players - 1

		if interaction:
			await interaction.response.edit_message(view=self)
		elif self.message:
			await self.message.edit(view=self)

	@discord.ui.button(label="+", style=discord.ButtonStyle.green, row=0, custom_id="mafia_up")
	async def mafia_add(self, interaction: discord.Interaction, _):
		total_players = len(self.game.abstractor.players)
		self.game.config["mafia"] = min(self.game.config["mafia"] + 1, total_players - 3)
		# If town + mafia exceeds total, auto-decrement town
		if self.game.config["town"] + self.game.config["mafia"] > total_players:
			self.game.config["town"] = max(1, total_players - self.game.config["mafia"])
		await self.render(interaction)

	@discord.ui.button(label="🔪 (1)", style=discord.ButtonStyle.gray, row=0, custom_id="mafia_display", disabled=True)
	async def mafia_display(self, i, b): pass

	@discord.ui.button(label="+", style=discord.ButtonStyle.green, row=1, custom_id="town_up")
	async def town_add(self, interaction: discord.Interaction, _):
		total_players = len(self.game.abstractor.players)
		self.game.config["town"] = min(self.game.config["town"] + 1, total_players - 1)
		# If town + mafia exceeds total, auto-decrement mafia
		if self.game.config["town"] + self.game.config["mafia"] > total_players:
			self.game.config["mafia"] = max(1, total_players - self.game.config["town"])
		await self.render(interaction)

	@discord.ui.button(label="🏡 (1)", style=discord.ButtonStyle.gray, row=1, custom_id="town_display", disabled=True)
	async def town_display(self, i, b): pass

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

		lines = []
		for name in view.player_names:
			count = sum(1 for v in view.votes.values() if v == name)
			if count:
				lines.append(f"- {name}: {count}")

		if view.allow_abstain:
			abstain_count = sum(1 for v in view.votes.values() if v == ABSTAIN_LABEL)
			if abstain_count:
				lines.append(f"- {ABSTAIN_LABEL}: {abstain_count}")

		if not lines:
			lines = ["No votes yet."]

		content = view.base_message + "\n" + "\n\n**Votes:**\n" + "\n".join(lines)

		# If everyone has voted, disable the select
		if sum(1 for uid in view.votes.keys() if uid in view.allowed_voters) >= view.required_votes:
			self.disabled = True

		await interaction.response.edit_message(content=content, view=view)

class VoteView(discord.ui.View):
	def __init__(self, players: list[str], placeholder="Vote on a player.", emoji="🗳️", allow_abstain: bool = False):
		super().__init__(timeout=None)
		self.allow_abstain = allow_abstain
		self.add_item(VoteSelect(players, placeholder, emoji, allow_abstain=allow_abstain))
		self.votes: dict[int, str] = {}
		self.allowed_voters: set[int] = set()
		self.required_votes: int = 0
		self.base_message: str = ""
		self.player_names: list[str] = players

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
		self.save_queue = asyncio.Queue()
		self.investigate_queue = asyncio.Queue()
		self.client = None  # Will be set by game.py
		self.turn_manager = None  # Will be set by game.py for broadcasting
		self.sheriff_already_done = False
		self.doctor_already_done = False

	def get(self, id):
		return discord.utils.get(self.children, custom_id=id)

	def get_doctor_save(self):
		return self.save_queue.get()

	def get_sheriff_investigate(self):
		return self.investigate_queue.get()

	async def on_save_selected(self, interaction: discord.Interaction):
		user = self.players[int(self.doctor_selector.dropdown.values[0])]
		await interaction.response.edit_message(content=f"You chose to save {user.name}.", view=None)
		await self.save_queue.put(user)

	async def on_investigation_selected(self, interaction: discord.Interaction):
		user = self.players[int(self.sheriff_selector.dropdown.values[0])]
		await interaction.response.edit_message(content=f"You chose to investigate {user.name}. {user.name} is **{user.role.alignment().upper()}**!", view=None)
		await self.investigate_queue.put(user)

	async def handle_ai_doctor_action(self, doctor: Player):
		"""Handle AI doctor choosing who to save."""
		if not self.client:
			return

		messages = self.turn_manager.context[doctor.user] if self.turn_manager else []

		prompt = f"""During the night, as the Doctor, you must choose one player to save from being killed by the Mafia.

Available players to save:
{chr(10).join([f"- {p.name}" for p in self.players if p.alive])}

Remember: You cannot see who the Mafia will target, but if you save the same person they target, you prevent their death.
You can save yourself, but it's often better to protect someone you think the Mafia might target.

Who do you want to save? Reply with EXACTLY ONE player name, nothing else."""

		messages.append({"role": "user", "content": prompt})

		try:
			response = await self.client.chat.completions.create(
				model=doctor.user.model,
				messages=messages
			)
			choice_text = (response.choices[0].message.content or "").strip()

			# Find matching player
			chosen = None
			for p in self.players:
				if p.alive and p.name.lower() in choice_text.lower():
					chosen = p
					break

			if not chosen:
				chosen = next((p for p in self.players if p.alive), None)

			if chosen:
				await self.save_queue.put(chosen)
				messages.append({"role": "assistant", "content": chosen.name})
				if self.turn_manager:
					self.turn_manager.broadcast("Doctor made their choice for the night.")
		except Exception as e:
			logger.error(f"Error getting AI doctor action: {e}")

	async def handle_ai_sheriff_action(self, sheriff: Player):
		"""Handle AI sheriff choosing who to investigate."""
		if not self.client:
			return

		messages = self.turn_manager.context[sheriff.user] if self.turn_manager else []

		prompt = f"""During the night, as the Sheriff, you can investigate one player to learn if they are part of the Mafia or with the Town.

Available players to investigate:
{chr(10).join([f"- {p.name}" for p in self.players if p.alive and p != sheriff])}

Choose wisely - this information will help the town during the day. You might want to investigate someone acting suspiciously.

Who do you want to investigate? Reply with EXACTLY ONE player name, nothing else."""

		messages.append({"role": "user", "content": prompt})

		try:
			response = await self.client.chat.completions.create(
				model=sheriff.user.model,
				messages=messages
			)
			choice_text = (response.choices[0].message.content or "").strip()

			# Find matching player
			chosen = None
			for p in self.players:
				if p.alive and p != sheriff and p.name.lower() in choice_text.lower():
					chosen = p
					break

			if not chosen:
				chosen = next((p for p in self.players if p.alive and p != sheriff), None)

			if chosen:
				await self.investigate_queue.put(chosen)
				messages.append({"role": "assistant", "content": chosen.name})
				messages.append({"role": "user", "content": f"{chosen.name} is **{chosen.role.alignment().upper()}**."})
				if self.turn_manager:
					self.turn_manager.broadcast("Sheriff made their choice for the night.")
		except Exception as e:
			logger.error(f"Error getting AI sheriff action: {e}")

	@discord.ui.button(label="Doctor", style=discord.ButtonStyle.blurple, emoji="🧑‍⚕️", custom_id="doctor")
	async def doctor_save(self, interaction: discord.Interaction, _):
		if interaction.user.id not in [p.user.id for p in self.players if p.role == Role.DOCTOR]:
			await interaction.response.send_message("Not for you.", ephemeral=True)
			return
		elif self.doctor_already_done:
			await interaction.response.send_message("You already saved someone!", ephemeral=True)

		self.doctor_selector = SelectView([
			discord.components.SelectOption(
				label=self.players[i].name,
				value=str(i),
				emoji="💊"
			)
			for i in range(len(self.players))
		], self.on_save_selected)

		await interaction.response.send_message("## Doctor\nWho do you want to save?", view=self.doctor_selector, ephemeral=True)
		self.doctor_already_done = True

	@discord.ui.button(label="Sheriff", style=discord.ButtonStyle.grey, emoji="🤠", custom_id="sheriff")
	async def sheriff_investigate(self, interaction: discord.Interaction, _):
		if interaction.user.id not in [p.user.id for p in self.players if p.role == Role.SHERIFF]:
			await interaction.response.send_message("Not for you.", ephemeral=True)
			return
		elif self.sheriff_already_done:
			await interaction.response.send_message("You already investigated!", ephemeral=True)

		self.sheriff_selector = SelectView([
			discord.components.SelectOption(
				label=self.players[i].name,
				value=str(i),
				emoji="🕵️"
			)
			for i in range(len(self.players))
		], self.on_investigation_selected)

		await interaction.response.send_message("## Sheriff\nWho do you want to investigate?", view=self.sheriff_selector, ephemeral=True)
		self.sheriff_already_done = True
