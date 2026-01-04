import discord, logging, data
from classes.views import StartGameView

logger = logging.getLogger(__name__)

class GameAbstractor:
	players: list[discord.User] = []
	running = False
	last_lobby: discord.Message = None

	def __init__(self, channel: int):
		self.channel = channel
		config = data.load()
		self.last_lobby = config.get("last_lobbies", {self.channel: None})[self.channel]
	
	async def on_message(self, message: discord.Message):
		if message.channel.id != self.channel: return
		
		if not self.running:
			if self.last_lobby:
				await self.last_lobby.delete()
			
			self.last_lobby = await message.channel.send(embed=discord.Embed(
				title="AI Plays Mafia",
				description="The series by Turing Games, now as a Discord bot!",
				color=discord.Color.blurple()
			), view=StartGameView(self))

			config = data.load()
			if "last_lobbies" in config:
				config.last_lobbies[self.channel] = self.last_lobby.id
			else:
				config["last_lobbies"] = {self.channel: self.last_lobby.id}
		else:
			logger.info("Skipping message send as the game is already running!")