from discord.ext import commands
from discord import app_commands
import discord, platform, psutil

class InfoCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@app_commands.command(name="ping", description="ping pong")
	async def hello(self, interaction: discord.Interaction):
		await interaction.response.send_message(f"🏓 Pong!\nLatency: %.2fms" % self.bot.latency)
	
	@app_commands.command(name="echo", description="Say something as the bot")
	async def echo(self, interaction: discord.Interaction, text: str):
		await interaction.response.send_message(text)
	
	@app_commands.command(name="info", description="View bot information and stats")
	async def info(self, interaction: discord.Interaction):
		embed = discord.Embed(
			title="Info"
		)
		embed.add_field(name="System", value=f"""
			OS version: `{platform.platform()}`
			Python version: `{platform.python_version()}`
			discord.py version: `{discord.__version__}`
			CPU usage: `{psutil.cpu_percent(interval=1)}%`
			RAM usage: `{psutil.virtual_memory().percent}%`
		""", inline=False)
		embed.add_field(name="Credits", value=f"""
			Original series by Turing Games ([YouTube](https://www.youtube.com/@turing_games))
			Bot adaption by <@1337909802931716197>
			Icons from [lucide.dev](https://lucide.dev)
			[GitHub](https://github.com/redisnotbluedev/discord-mafia)
		""", inline=False)

		await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())
