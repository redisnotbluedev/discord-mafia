from discord.ext import commands
from discord import app_commands
import discord

class GamesCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot: commands.Bot = bot

	@app_commands.command(name="kick", description="Kick a player from this game.")
	async def kick(self, interaction: discord.Interaction, player: discord.User):
		if interaction.user == player:
			await interaction.response.send_message("You can't kick yourself.", ephemeral=True)
			return

		abstractor = next((a for a in self.bot.abstractors if a.channel == interaction.channel.id), None)
		if abstractor:
			if abstractor.owner == interaction.user:
				del abstractor.players[player.id]
				scheduler = abstractor.game.scheduler
				scheduler.message.edit(embed=scheduler.lobby.generate_embed())
			else:
				await interaction.response.send_message("You need to be the owner of this game to kick players.", ephemeral=True)
		else:
			await interaction.response.send_message("There's no ongoing game in this channel.", ephemeral=True)
