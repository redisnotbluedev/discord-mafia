from discord.ext import commands
from discord import app_commands
import discord, platform, psutil, asyncio, os

class InfoCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot: commands.Bot = bot

	@app_commands.command(name="ping", description="ping pong")
	async def hello(self, interaction: discord.Interaction):
		await interaction.response.send_message("🏓 Pong!\nLatency: %.2fms" % (self.bot.latency * 1000))

	@app_commands.command(name="echo", description="Say something as the bot")
	async def echo(self, interaction: discord.Interaction, text: str, channel: discord.TextChannel):
		if str(interaction.user.id) not in os.getenv("ADMIN_USERS").split(","):
			await interaction.response.send_message("<:pointlaugh:1474657622509486130> You're not allowed to use this command!", ephemeral=True)
			return
		await asyncio.gather(*[interaction.response.send_message("Sent message!", ephemeral=True), channel.send(text)])

	@app_commands.command(name="info", description="View bot information and stats")
	async def info(self, interaction: discord.Interaction):
		embed = discord.Embed(
			title="Info"
		)
		embed.add_field(name="System", value=f"""
			<:os:1474653478054793236> OS version: `{platform.platform()}`
			<:python:1474654225958174772> Python version: `{platform.python_version()}`
			<:discord:1474654699163488357> discord.py version: `{discord.__version__}`
			<:cpu:1474654894538362981> CPU usage: `{psutil.cpu_percent(interval=1)}%`
			<:ram:1474654986926293076> RAM usage: `{psutil.virtual_memory().percent}%`
		""", inline=False)
		embed.add_field(name="Credits", value="""
			<:owner:1474651989798289488> Original series by Turing Games ([YouTube](https://www.youtube.com/@turing_games))
			<:bot:1474641567032676402> Bot created by <@1337909802931716197>
			<:developer:1474641229743657085> Developers: <@750631921079287839> & <@1282734265955520545>
			<:tester:1474652259001569474> Playtesters: <@503232391993622540>, SpaceKiwi, lolcaku, Nanji & SilverArrow
		""", inline=False)
		embed.add_field(name="Info", value="""
			<:wifi:1474651483109855334> this bot literally runs on my trash home wifi in australia the ping is terrible sorry
			<:github:1474644220353445898> Source code on [GitHub](https://github.com/redisnotbluedev/discord-mafia)
		""")

		await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())
