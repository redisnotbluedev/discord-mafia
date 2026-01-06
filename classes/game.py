from classes.abstractor import GameAbstractor
import asyncio, time, discord

class MafiaGame:
	def __init__(self, abstractor: GameAbstractor):
		from classes.views import JoinGameView

		self.abstractor = abstractor
		self.lobby: JoinGameView = None
		self.message: discord.Message = None
		self.players = {}
		self.config = {}
	
	def schedule(self, start_at: int):
		async def task():
			await asyncio.sleep(start_at - time.time())
			if not await self.start_game():
				await self.message.channel.send("Not enough players to start the game!")
				self.lobby.start_at = int(time.time()) + 60 * 5
				await self.message.edit(embed=self.lobby.generate_embed())
				self.schedule(self.lobby.start_at)
		
		asyncio.create_task(task())

	async def start_game(self):
		if len(self.players) < 5: return False

		bot = self.abstractor.bot

		for player in self.players:
			pass
		
		await bot.get_channel(self.abstractor.channel).send("Starting game...")