import discord, logging
from classes.views import StartGameView

logger = logging.getLogger(__name__)

class GameAbstractor:
	players: list[discord.User] = []
	running = False
	last_lobby: discord.Message = None

	def __init__(self, channel: int):
		self.channel = channel
	
	async def on_message(self, message: discord.Message):
		if message.channel.id != self.channel: return
		
		if not self.running:
			if self.last_lobby:
				self.last_lobby.delete()
			
			self.last_lobby = await message.channel.send(embed=discord.Embed(
				title="AI Plays Mafia",
				description="The series by Turing Games, now as a Discord bot!",
				color=discord.Color.blurple()
			), view=StartGameView(self))
		else:
			logger.info("Skipping message send as the game is already running!")