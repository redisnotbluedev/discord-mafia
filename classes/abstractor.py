import discord
from views import StartGameView

class GameAbstractor:
	players: list[discord.User] = []
	running = False

	def __init__(self, channel: int):
		self.channel = channel
	
	async def on_message(self, message: discord.Message):
		if message.channel != self.channel: return
		
		if not self.running:
			await message.channel.send(embed=discord.Embed(
				title="AI Plays Mafia",
				description="The series by Turing Games, now as a Discord bot!",
				color=discord.Color.blurple()
			), view=StartGameView(self.players))