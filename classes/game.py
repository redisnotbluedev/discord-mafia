from classes.player import Role, Player, AIAbstraction
from classes.turnmanager import TurnManager
from classes.views import SpecialActionsView
from openai import AsyncOpenAI
import logging, discord, asyncio

logger = logging.getLogger(__name__)

class MafiaGame():
	def __init__(self, abstractor):
		self.players = []
		self.day_number = 0
		self.night_actions = {}
		self.current_phase: str | None = None
		self.current_night_id: int = 0
		self.channel: discord.Channel = None   # todo
		self.mafia_chat: discord.Thread = None # todo

		self.turns: TurnManager = None
		self.bot: discord.Client = abstractor.bot
		self.generator: AsyncOpenAI = AsyncOpenAI()

	def get_alive_players(self) -> list[Player]:
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

		# Announce roles to all AIs
		await self._broadcast_initial_roles()

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

	async def _broadcast_initial_roles(self):
		"""Tell all AIs what their roles are at game start."""
		for player in self.players:
			if isinstance(player.user, AIAbstraction):
				role_desc = player.role.describe()
				message = f"**Game Started!** You are {role_desc}\n\nOther players: {', '.join([p.name for p in self.players if p != player])}"
				self.turns.context[player.user].append({"role": "user", "content": message})
		await asyncio.sleep(0)  # Yield to event loop

	async def run_night_phase(self):
		self.current_phase = "night"
		self.current_night_id += 1
		await self.channel.send(f"**Night {self.day_number} falls...**")
		alive_players = self.get_alive_players()

		# Broadcast alive players and night phase info to AIs
		alive_names = [p.name for p in alive_players]
		self.turns.broadcast(f"Night {self.day_number} has begun. Alive players: {', '.join(alive_names)}. Special roles (Doctor, Sheriff), prepare your actions.")

		# Find special role players
		doctor = next((p for p in alive_players if p.role == Role.DOCTOR), None)
		sheriff = next((p for p in alive_players if p.role == Role.SHERIFF), None)

		roles = []
		if doctor:
			roles.append("Doctor")
		if sheriff:
			roles.append("Sheriff")

		tasks = [self.mafia_choose_target()]

		actions_view = SpecialActionsView(alive_players, self, self.current_night_id)
		actions_view.turn_manager = self.turns
		actions_view.client = self.generator

		if roles:
			actions_message = await self.channel.send(
				f"## Night Actions\n{
					(lambda vals: f"{", ".join(vals[:-1])} and {vals[-1]}" if len(vals) > 1 else vals[0])(roles)
				}, click the buttons below to do your night actions. Mafia, talk in {self.mafia_chat.jump_url}.",
				view=actions_view
			)
			actions_view.actions_message = actions_message

			async def update_night_action(key, getter):
				self.night_actions[key] = await getter

			# Handle Doctor's action (AI or human)
			if doctor:
				if isinstance(doctor.user, AIAbstraction):
					tasks.append(update_night_action("doctor_save", actions_view.handle_ai_doctor_action(doctor)))
				else:
					tasks.append(update_night_action("doctor_save", actions_view.get_doctor_save()))

			# Handle Sheriff's action (AI or human)
			if sheriff:
				if isinstance(sheriff.user, AIAbstraction):
					tasks.append(update_night_action("sheriff_investigate", actions_view.handle_ai_sheriff_action(sheriff)))
				else:
					tasks.append(update_night_action("sheriff_investigate", actions_view.get_sheriff_investigate()))

		await asyncio.gather(*tasks)

		# Broadcast results to AIs
		kill = self.night_actions.get("mafia_kill")
		save = self.night_actions.get("doctor_save")

		if kill and kill != save:
			kill.alive = False
			message = f"{kill.name} was killed by the Mafia during the night."
			await self.channel.send(f"> {message}\n-# {len(self.get_alive_players())} players left.")
			self.turns.broadcast(message)
		else:
			message = "Nobody was killed last night. Either the Doctor saved the target, or the Mafia didn't send a kill."
			await self.channel.send(message)
			self.turns.broadcast(message)

		# Broadcast sheriff findings to AIs
		sheriff_target = self.night_actions.get("sheriff_investigate")
		if sheriff_target:
			finding = f"The Sheriff investigated {sheriff_target.name} and found they are {sheriff_target.role.alignment()}."
			self.turns.broadcast(finding)

		self.night_actions.clear()
		self.current_phase = "day"

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
		mafia = [p for p in alive if p.role == Role.MAFIA]

		self.turns.set_channel(self.mafia_chat)
		self.turns.set_participants(mafia)

		# Broadcast to Mafia members who is in the group
		mafia_names = [p.name for p in mafia]
		self.turns.broadcast(f"You are part of the Mafia! Your team consists of: {', '.join(mafia_names)}. Choose wisely who to eliminate.")

		await self.turns.run_round()

		targets = [p for p in alive if p.role != Role.MAFIA]
		kill = await self.turns.run_vote(
			candidates=targets,
			message=f"Night {self.day_number}: Mafia, choose a kill target.",
			placeholder="Choose a target...",
			emoji="🔪",
			break_ties_random=True,
		)

		self.night_actions["mafia_kill"] = kill

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
		await self.turns.run_round()

	async def voting_phase(self):
		alive = self.get_alive_players()
		# day lynch vote: allow abstain, no random tie-break; abstain/none highest => no lynch

		# Broadcast voting phase to AIs
		self.turns.broadcast("It's time to vote! Based on the discussion, who do you think should be eliminated?")

		victim = await self.turns.run_vote(
			candidates=alive,
			message=f"Day {self.day_number}: Vote to eliminate a player.",
			placeholder="Vote for a player...",
			emoji="🗳️",
			allow_abstain=True
		)

		if victim:
			message = f"{victim.name} was voted out and eliminated. They were {victim.role}."
			self.turns.broadcast(message)
		else:
			message = "Nobody was voted out today. The vote was inconclusive or everyone abstained."
			self.turns.broadcast(message)

		return victim
