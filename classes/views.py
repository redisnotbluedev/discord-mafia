import discord

class ConfirmView(discord.ui.View):
	def __init__(self, yes, no):
		self.yes = yes
		self.no = no
		super().__init__(timeout=300)
	
	@discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
	async def on_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
		await self.yes(interaction)
	
	@discord.ui.button(label="No", style=discord.ButtonStyle.red)
	async def on_no(self, interaction: discord.Interaction, button: discord.ui.Button):
		await self.no(interaction)

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

	@discord.ui.button(label="Join/Leave", style=discord.ButtonStyle.green)
	async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)
		embed.add_field(name="Players", value="\n".join([f"- {u.display_name or u.name}" for u in self.abstractor.players]))

		if interaction.user in self.abstractor.players:
			async def yes(i: discord.Interaction):
				await i.response.edit_message(content="You left the game.", view=None)
				await interaction.message.edit_message(embed=embed)
				
			async def no(i: discord.Interaction):
				await i.response.edit_message(content="You canceled this action.", view=None)
			
			await interaction.response.send_message(
				content="Are you sure you want to leave the game?\nYou can always re-join after.",
				view=ConfirmView(yes, no),
				ephemeral=True
			)
		else:
			self.abstractor.players.append(interaction.user)
			await interaction.response.edit_message(embed=embed)