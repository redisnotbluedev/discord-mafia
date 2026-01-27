from classes.roles import MAFIA, Alignment
from classes.player import Player, AIAbstraction
from classes.turnmanager import TurnManager
from classes.views import SpecialActionsView
from openai import AsyncOpenAI
import logging, discord, asyncio

logger = logging.getLogger(__name__)

sheriff_already_done = False
doctor_already_done = False

class MafiaGame():
	def __init__(self, abstractor):
		self.players = []
		self.day_number = 0
		self.night_actions = {}
		self.config = {}
		self.channel: discord.Channel = None   # todo
		self.mafia_chat: discord.Thread = None # todo
		self.running = False

		self.turns: TurnManager = None
		self.bot: discord.Client = abstractor.bot
		self.generator: AsyncOpenAI = AsyncOpenAI()

	def get_alive_players(self) -> list[Player]:
		return [p for p in self.players if p.alive]

	def is_game_over(self):
		players_alive = self.get_alive_players()

		# Check role win conditions
		for player in self.players:
			if player.role.win_condition(player, self.players):
				return player.role.name

		# Fallback to traditional checks
		mafia_alive = sum(1 for p in players_alive if p.role.alignment == Alignment.MAFIA)
		town_alive = len(players_alive) - mafia_alive

		if mafia_alive == 0:
			return "Town"
		if mafia_alive >= town_alive:
			return "Mafia"

		return False

	async def run(self):
		self.running = True
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

		winner = self.is_game_over() or "No one"
		# Broadcast game end to all AIs
		self.turns.broadcast(f"**GAME OVER!** {winner} wins!")
		return winner

	async def run_night_phase(self):
		await self.channel.send(f"**Night {self.day_number} falls...**")
		alive_players = self.get_alive_players()

		# Find special role players
		special_players = [p for p in alive_players if p.role.is_special()]

		roles = list(set(p.role.name for p in special_players))

		tasks = [self.mafia_choose_target()]

		actions_view = SpecialActionsView(alive_players)
		actions_view.turn_manager = self.turns
		actions_view.game = self

		# Always send the night message with Mafia chat link
		message = f"## Night Actions\nMafia, talk in {self.mafia_chat.jump_url}."
		if roles:
			message += f"\n{(lambda vals: f"{", ".join(vals[:-1])} and {vals[-1]}" if len(vals) > 1 else vals[0])(roles)}, click the buttons below to do your night actions."

		await self.channel.send(message, view=actions_view)

		# Handle AI special actions
		for player in special_players:
			if isinstance(player.user, AIAbstraction):
				tasks.append(actions_view.handle_ai_special_action(player))
			# Human actions are handled by the role buttons

		await asyncio.gather(*tasks) # all the night actions should be concurrent

		# Process night actions
		kill = self.night_actions.get("mafia_kill")
		saves = self.night_actions.get("saves", [])
		vigilante_kills = self.night_actions.get("kills", [])

		# Apply vigilante kills
		for victim in vigilante_kills:
			if victim and victim.alive:
				victim.alive = False
				victim.death_reason = "vigilante"
				message = f"{victim.name} was killed by the Vigilante during the night. They were {victim.role}."
				await self.channel.send(f"> {message}\n-# {len(self.get_alive_players())} players left.")
				self.turns.broadcast(message)

		# Check mafia kill
		if kill and kill not in saves and kill.alive:
			kill.alive = False
			kill.death_reason = "mafia"
			message = f"{kill.name} was killed by the Mafia during the night. They were {kill.role}."
			await self.channel.send(f"> {message}\n-# {len(self.get_alive_players())} players left.")
			self.turns.broadcast(message)
		elif kill:
			message = f"{kill.name} was attacked by the Mafia but was saved!"
			await self.channel.send(message)
			self.turns.broadcast(message)
		else:
			message = "Nobody was killed last night. Either someone saved the target, or the Mafia didn't send a kill."
			await self.channel.send(message)
			self.turns.broadcast(message)

		self.night_actions.clear()

	async def run_day_phase(self):
		if not self.get_alive_players():
			return

		await self.discussion_phase()
		victim = await self.voting_phase()

		if victim:
			victim.alive = False
			message = f"{victim.name} was eliminated! They were {victim.role}."
			await self.channel.send(f"> **{message}**")
			self.turns.broadcast(message)
		else:
			message = "No one was eliminated."
			await self.channel.send(message)
			self.turns.broadcast(message)

	async def mafia_choose_target(self):
		alive = self.get_alive_players()
		mafia = [p for p in alive if p.role == MAFIA]

		self.turns.set_channel(self.mafia_chat)
		self.turns.set_participants(mafia)

		# Broadcast to Mafia members who is in the group
		mafia_names = [p.name for p in mafia]
		self.turns.broadcast(f"You are part of the Mafia! Your team consists of: {', '.join(mafia_names)}. Choose wisely who to eliminate.")

		await self.turns.run_round()

		targets = [p for p in alive if p.role != MAFIA]
		kill = await self.turns.run_vote(
			candidates=targets,
			message=f"Night {self.day_number}: Mafia, choose a kill target.",
			placeholder="Choose a target...",
			emoji="🔪",
			break_ties_random=True,
		)

		self.night_actions["mafia_kill"] = kill
		self.turns.set_channel(self.channel)
		self.turns.set_participants(alive)

	async def discussion_phase(self):
		alive = self.get_alive_players()
		# reuse the main turn manager for day discussion
		if not self.turns:
			self.turns = TurnManager(
				alive,
				self.channel,
				self.bot,
				self.generator
			)
		else:
			self.turns.set_channel(self.channel)
			self.turns.set_participants(alive)

		# Broadcast day phase start to AIs with context
		alive_names = [p.name for p in alive]
		self.turns.broadcast(f"Day {self.day_number} has begun. Alive players: {', '.join(alive_names)}. It's discussion time. Pay close attention to what others say and how they behave - look for suspicious activity or patterns.")

		await self.channel.send(f"**Day {self.day_number} begins...**")
		for _ in range(2):
			await self.turns.run_round()

	async def voting_phase(self):
		alive = self.get_alive_players()
		# day lynch vote: allow abstain, no random tie-break; abstain/none highest => no lynch

		victim = await self.turns.run_vote(
			candidates=alive,
			message=f"Day {self.day_number}: Vote to eliminate a player.",
			placeholder="Vote for a player...",
			emoji="🗳️",
			allow_abstain=True
		)

		if victim:
			victim.alive = False
			victim.death_reason = "lynch"
			message = f"{victim.name} was voted out and eliminated. They were {victim.role}."
			self.turns.broadcast(message)
		else:
			message = "Nobody was voted out today. The vote was inconclusive or everyone abstained."
			self.turns.broadcast(message)

		return victim
