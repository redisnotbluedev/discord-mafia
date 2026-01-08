from classes.player import Role
import asyncio, logging

logger = logging.getLogger(__name__)

class MafiaGame():
	def __init__(self):
		self.players = []
		self.day_number = 0
		self.night_actions = {}
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
	
	async def run_night_phase(self):
		await self.send(f"**Night {self.day_number} falls...**")

		tasks = [self.mafia_choose_target()]
		players = self.get_alive_players()
		if sum(1 for p in players if p.role == Role.DOCTOR): tasks.append(self.doctor_choose_save())
		if sum(1 for p in players if p.role == Role.SHERIFF): tasks.append(self.sheriff_investigate())
		await asyncio.gather(*tasks)

		kill = self.night_actions.get("mafia_kill")
		save = self.night_actions.get("doctor_save")

		if kill and kill != save:
			kill.alive = False
			await self.send(f"""> {
				kill.user.display_name or kill.user.name
			} was killed by the Mafia.
			-# {
				len(self.get_alive_players())
			} players left.""")
		else:
			await self.send("Nobody died last night.")
		
		self.night_actions.clear()
	
	async def run_day_phase(self):
		pass