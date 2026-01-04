import discord, logging, data
from classes.views import StartGameView
from discord.ext import commands

logger = logging.getLogger(__name__)

class GameAbstractor:
	players: list[discord.User] = []
	running = False
	last_lobby: int = None

	def __init__(self, channel: int, bot: commands.Bot):
		self.channel = channel
		self.channel_key = str(channel)
		self.bot = bot

		config = data.load()
		self.last_lobby = config.get("last_lobbies", {}).get(self.channel_key, None)

	async def on_message(self, message: discord.Message):
		if message.channel.id != self.channel:
			return

		if not self.running:
			if self.last_lobby:
				await (await self.bot.get_channel(self.channel).fetch_message(self.last_lobby)).delete()

			self.last_lobby = (await message.channel.send(
				embed=discord.Embed(
					title="AI Plays Mafia",
					description="The series by Turing Games, now as a Discord bot!",
					color=discord.Color.blurple(),
				),
				view=StartGameView(self),
			)).id

			config = data.load()
			last_lobbies = config.setdefault("last_lobbies", {})
			last_lobbies[self.channel_key] = self.last_lobby.id
			data.save(config)
		else:
			logger.info("Skipping message send as the game is already running!")