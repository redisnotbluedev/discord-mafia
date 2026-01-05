import discord, time
from classes.game import MafiaGame
from classes.abstractor import GameAbstractor

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
		super().__init__(timeout=300)

	@discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
	async def start_game(self, interaction: discord.Interaction, _):
		if self.abstractor.running:
			return

		self.abstractor.players.append(interaction.user)
		
		self.abstractor.running = True
		self.abstractor.last_lobby_id = None
		self.abstractor.owner = interaction.user
		self.abstractor.save_config()

		view = JoinGameView(self.abstractor, time.time() + 60 * 5)
		embed = view.generate_embed()

		await interaction.response.edit_message(embed=embed, view=view)

class JoinGameView(discord.ui.View):
	def __init__(self, abstractor, start_at):
		self.abstractor: GameAbstractor = abstractor
		self.start_at = int(start_at)
		self.game = MafiaGame(self.abstractor)
		self.game.schedule(start_at)
		super().__init__(timeout=300)

	def generate_embed(self):
		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)

		embed.add_field(name="Starting soon", value=f"Game starting <t:{self.start_at}:R>\nNeed at least ({len(self.abstractor.players)}/5) players to start", inline=False)
		embed.add_field(name="Players", value="\n".join([f"- {"<:owner:1457538443327311872> " if u == self.abstractor.owner else ""}{u.display_name or u.name}" for u in self.abstractor.players]) if self.abstractor.players else "No players yet!")

		return embed

	@discord.ui.button(label="Join/Leave", style=discord.ButtonStyle.blurple)
	async def join_game(self, interaction: discord.Interaction, _):
		if interaction.user in self.abstractor.players:
			async def yes(i: discord.Interaction):
				await i.response.edit_message(content="You left the game.", view=None)
				self.abstractor.players.remove(interaction.user)

				if interaction.user == self.abstractor.owner:
					await interaction.message.edit(
						embed=discord.Embed(
							title="AI Plays Mafia",
							description="The series by Turing Games, now as a Discord bot!",
							color=discord.Color.blurple(),
						),
						view=StartGameView(self.abstractor)
					)
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
			self.abstractor.players.append(interaction.user)
			embed = self.generate_embed()
			await interaction.response.edit_message(embed=embed)
	
	@discord.ui.button(emoji=discord.PartialEmoji(name="settings", id=1457586025105850470), style=discord.ButtonStyle.gray)
	async def settings(self, interaction: discord.Interaction, _):
		if interaction.user != self.abstractor.owner:
			await interaction.response.send_message("You need to be the owner of this game to change the settings.", ephemeral=True)
			return
		
		view = SettingsView(self.game)
		view.render()
		await interaction.response.send_message(
			embed=discord.Embed(title="Settings", description="Change the configuration of this game."),
			view=view,
			ephemeral=True
		)

class SettingsView(discord.ui.View):
	def __init__(self, game: MafiaGame):
		self.game = game
	
	async def render(self, message: discord.Message):
		self.town.label = self.game.config.get("town", self.game.abstractor.players // 2)
		message.edit(view=self)

	@discord.ui.button(label="-", style=discord.ButtonStyle.red, row=0)
	async def town_subtract(self, interaction: discord.Interaction, _):
		pass

	@discord.ui.button(label="0", disabled=True, row=0)
	async def town(self, interaction: discord.Interaction, _): pass

	@discord.ui.button(label="+", style=discord.ButtonStyle.green, row=0)
	async def town_add(self, interaction: discord.Interaction, _):
		pass