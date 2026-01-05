import discord

class StartGameView(discord.ui.View):
	def __init__(self, abstractor):
		self.abstractor = abstractor
		super().__init__(timeout=300)

	@discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
	async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)
		
		self.abstractor.players.append(interaction.user)
		embed.add_field(name="Players", value=f"- {interaction.user.display_name or interaction.user.name}", inline=False)
		
		self.abstractor.running = True
		self.abstractor.last_lobby_id = None
		self.abstractor.save_config()
		
		await interaction.response.edit_message(embed=embed, view=JoinGameView(self.abstractor))

class JoinGameView(discord.ui.View):
	def __init__(self, abstractor):
		self.abstractor = abstractor
		super().__init__(timeout=300)

	@discord.ui.button(label="Join", style=discord.ButtonStyle.secondary)
	async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
		if interaction.user in self.abstractor.players:
			await interaction.response.send_message("You're already in the game!", ephemeral=True)
			return

		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)
		self.abstractor.players.append(interaction.user)
		embed.add_field(name="Players", value="\n".join([f"- {u.display_name or u.name}" for u in self.abstractor.players]))
		await interaction.response.edit_message(embed=embed)