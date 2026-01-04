from discord.ext import commands
from discord import app_commands
import discord

class InfoCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@app_commands.command(name="ping", description="ping pong")
	async def hello(self, interaction: discord.Interaction):
		await interaction.response.send_message(f"🏓 Pong!\nLatency: %.2fms" % self.bot.latency)
	
	@app_commands.command(name="echo", description="Say something as the bot")
	async def echo(self, interaction: discord.Interaction, text: str):
		await interaction.response.send_message(text)