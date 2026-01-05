from classes.abstractor import GameAbstractor
import asyncio, time

class MafiaGame:
	def __init__(self, abstractor: GameAbstractor):
		self.abstractor = abstractor
	
	def schedule(self, start_at: int):
		async def task():
			await asyncio.sleep(start_at - time.time())
			await self.start_game()
		
		asyncio.create_task(task())

	async def start_game(self):
		bot = self.abstractor.bot
		await bot.get_channel(self.abstractor.channel).send("Starting game...")