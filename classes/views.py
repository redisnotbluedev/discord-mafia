import discord, time
from classes.game import MafiaGame
from classes.abstractor import GameAbstractor
from classes.player import Player, create_ai_players

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
		self.abstractor: GameAbstractor = abstractor
		super().__init__(timeout=None)

	@discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
	async def start_game(self, interaction: discord.Interaction, _):
		if self.abstractor.running:
			return

		self.abstractor.players[interaction.user.id] = Player(interaction.user)
		for ai_player in create_ai_players():
			# Use hash of AI name as key since AIAbstraction doesn't have an id
			self.abstractor.players[hash(ai_player.user.name)] = ai_player
		
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
		self.abstractor: GameAbstractor = abstractor
		self.start_at = int(start_at)
		self.game = MafiaGame(self.abstractor)
		self.game.message = message
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
			self.abstractor.players[interaction.user.id] = Player(interaction.user)
			embed = self.generate_embed()
			await interaction.response.edit_message(embed=embed)
	
	@discord.ui.button(label="Start Game", style=discord.ButtonStyle.green)
	async def start(self, interaction: discord.Interaction, _):
		self.game.start_job.cancel()
		self.game.schedule(time.time())
		await interaction.response.edit_message()

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
	def __init__(self, game: MafiaGame):
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