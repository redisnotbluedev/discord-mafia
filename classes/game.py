from classes.player import Role
from classes.turnmanager import TurnManager
import logging, discord, os
from openai import OpenAI

logger = logging.getLogger(__name__)

class MafiaGame():
	def __init__(self, abstractor):
		self.players = []
		self.day_number = 0
		self.night_actions = {}
		self.channel: discord.Channel = None   # todo
		self.mafia_chat: discord.Thread = None # todo

		self.turns: TurnManager = None
		self.mafia_turns: TurnManager = None
		self.bot: discord.Client = abstractor.bot
		self.generator: OpenAI = OpenAI(
			base_url="https://mapleai.de/v1",
			api_key=os.envget("MAPLEAI_API_KEY")
		)

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
		self.turns = TurnManager(
			self.players,
			self.channel,
			self.bot,
			self.generator
		)

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
		await self.channel.send(f"**Night {self.day_number} falls...**")

		tasks = [self.mafia_choose_target()]
		players = self.get_alive_players()
		if sum(1 for p in players if p.role == Role.DOCTOR): tasks.append(self.doctor_choose_save())
		if sum(1 for p in players if p.role == Role.SHERIFF): tasks.append(self.sheriff_investigate())

		kill = self.night_actions.get("mafia_kill")
		save = self.night_actions.get("doctor_save")

		if kill and kill != save:
			kill.alive = False
			await self.channel.send(f"""> {kill.name} was killed by the Mafia.
			-# {len(self.get_alive_players())} players left.""")
		else:
			await self.channel.send("Nobody died last night.")

		self.night_actions.clear()

	async def run_day_phase(self):
		if not self.get_alive_players():
			return

		await self.discussion_phase()
		victim = await self.voting_phase()

		if victim:
			victim.alive = False
			await self.channel.send(f"> **{victim.name}** was eliminated!\nThey were {victim.role}.")
		else:
			await self.channel.send("No one was eliminated.")

	async def mafia_choose_target(self):
		mafia = filter(p for p in self.players if p.role == Role.MAFIA)

		if not self.mafia_turns:
			self.mafia_turns = TurnManager(
				mafia,
				self.mafia_chat,
				self.bot,
				self.generator
			)

		await self.mafia_turns.run_round()

	async def doctor_choose_save(self):
		pass

	async def sheriff_investigate(self):
		pass

	async def discussion_phase(self):
		pass

	async def voting_phase(self):
		pass
