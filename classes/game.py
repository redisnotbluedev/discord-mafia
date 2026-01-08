from classes.player import Role

class MafiaGame():
	def __init__(self):
		self.players = []
		self.day_number = 0
		self.send: function = None
		self.mafia_send: function = None
	
	def get_alive_players(self):
		return [p for p in self.players if p.alive]

	def is_game_over(self):
		players_alive = self.get_alive_players()
		mafia_alive = sum(1 for p in players_alive if p.role == Role.MAFIA)
		town_alive = len(players_alive) - mafia_alive

		if mafia_alive == 0:
			return "Town"
		if mafia_alive >= town_alive:
			return "Mafia"
		
		return False

	async def run(self):
		while not self.is_game_over():
			self.day_number += 1
			
			await self.run_night_phase()
			if self.is_game_over():
				break
			
			await self.run_day_phase()
			if self.is_game_over():
				break

		return self.is_game_over() or "No one"