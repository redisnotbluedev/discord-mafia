"""Core game loop for Mafia.

Contains MafiaGame, which manages the night/day phase cycle, win
condition checks, and coordination between discussion, voting,
and special actions.
"""

from classes.roles import MAFIA, Alignment
from classes.player import Player, AIAbstraction
from classes.turnmanager import TurnManager
from classes.views import SpecialActionsView
from openai import AsyncOpenAI
import logging, discord, asyncio, time

logger = logging.getLogger(__name__)

# These are never read anywhere.
sheriff_already_done = False
doctor_already_done = False

class MafiaGame():
	"""Core game engine managing phases, win conditions, and game state.

	The game runs a loop of night → day phases until a win condition
	is met.  Each phase delegates to TurnManager for discussion/voting
	and to role-specific handlers for special night actions.

	Attributes:
		players: List of Player instances with assigned roles.
		day_number: Current day count (starts at 0, incremented on entry).
		night_actions: Dict collecting actions during the night phase
			(e.g. 'mafia_kill', 'saves', 'kills').  Cleared after resolution.
		config: Shared settings dict from MafiaScheduler/SettingsView.
		turns: TurnManager instance (created on first run).
	"""

	def __init__(self, abstractor, scheduler):
		"""Initialize a new game.

		Args:
			abstractor: The GameAbstractor for this channel.
			scheduler: The MafiaSheduler that owns this game, needed to
				access the JoinGameView for lobby updates.
		"""
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
		self.scheduler = scheduler

	def get_alive_players(self) -> list[Player]:
		"""Return the list of players who are still alive."""
		return [p for p in self.players if p.alive]

	def is_game_over(self):
		"""Check if any win condition has been met.

		Checks individual role win conditions first (e.g. Jester), then
		team-level conditions (all mafia dead = Town wins; mafia >= town
		= Mafia wins).

		Returns:
			The name of the winning faction/role (str), or False if the
			game is still going.  Returns 'No one' if the game isn't
			running at all.
		"""
		if not self.running:
			return "No one"

		players_alive = self.get_alive_players()

		for player in self.players:
			if player.role.win_condition(player, self.players):
				return player.role.name

		mafia_alive = sum(1 for p in players_alive if p.role.alignment == Alignment.MAFIA)
		town_alive = len(players_alive) - mafia_alive

		if mafia_alive == 0:
			return "Town"
		if mafia_alive >= town_alive:
			return "Mafia"

		return False

	async def run(self):
		"""Main game loop: alternate night and day until someone wins.

		Creates a TurnManager on first call and runs night → day in a
		loop, checking win conditions after each phase.

		Returns:
			The name of the winning faction/role (str).
		"""
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
		self.turns.broadcast(f"**GAME OVER!** {winner} wins!")
		return winner

	async def run_night_phase(self):
		"""Execute one night phase.

		1. Mafia discuss in their private thread and vote on a kill target
		   (runs concurrently with special actions).
		2. Special role holders (Doctor, Sheriff, Vigilante, etc.) perform
		   their actions via buttons or AI completions.
		3. Resolves kills and saves: Vigilante kills first, then Mafia
		   kill (blocked if Doctor saved the target).
		4. Calls on_night_end() for each player's role (used for
		   Jester win condition check).

		Side effects:
			Modifies player alive/death_reason state.
			Clears self.night_actions after resolution.
		"""
		await self.channel.send(f"**Night {self.day_number} falls...**")
		alive_players = self.get_alive_players()

		special_players = [p for p in alive_players if p.role.is_special()]

		roles = list(set(p.role.name for p in special_players))

		tasks = [self.mafia_choose_target()]

		actions_view = SpecialActionsView(alive_players)
		actions_view.turn_manager = self.turns
		actions_view.game = self

		timeout_at = int(time.time() + 180)
		message = f"## Night Actions\nMafia, talk in {self.mafia_chat.jump_url}."
		if roles:
			message += f"\n{(lambda vals: f"{", ".join(vals[:-1])} and {vals[-1]}" if len(vals) > 1 else vals[0])(roles)}, click the button(s) below to do your night actions."

		await self.channel.send(message, view=actions_view)

		for player in special_players:
			if isinstance(player.user, AIAbstraction):
				tasks.append(actions_view.handle_ai_special_action(player))

		await asyncio.gather(*tasks)

		await actions_view.wait_for_humans()

		kill = self.night_actions.get("mafia_kill")
		saves = self.night_actions.get("saves", [])
		vigilante_kills = self.night_actions.get("kills", [])

		for victim in vigilante_kills:
			if victim and victim.alive:
				victim.alive = False
				victim.death_reason = "vigilante"
				message = f"{victim.name} was killed by the Vigilante during the night. They were {victim.role}."
				await self.channel.send(f"> {message}\n-# {len(self.get_alive_players())} players left.")
				self.turns.broadcast(message)

		if kill:
			if kill not in saves and kill.alive:
				kill.alive = False
				kill.death_reason = "mafia"
				message = f"{kill.name} was killed by the Mafia during the night. They were {kill.role}."
				await self.channel.send(f"> {message}\n-# {len(self.get_alive_players())} players left.")
				self.turns.broadcast(message)
			elif kill in saves:
				message = f"{kill.name} was attacked by the Mafia but was saved!"
				await self.channel.send(message)
				self.turns.broadcast(message)
		elif not vigilante_kills:
			message = "Nobody was killed last night. Either someone saved the target, or the Mafia didn't send a kill."
			await self.channel.send(message)
			self.turns.broadcast(message)

		for p in self.players:
			await p.role.on_night_end(self, p)

		self.night_actions.clear()

	async def run_day_phase(self):
		"""Execute one day phase: discussion followed by a vote."""
		if not self.get_alive_players():
			return

		await self.discussion_phase()
		victim = await self.voting_phase()

		if victim:
			# voting_phase also sets this.
			victim.alive = False
			message = f"{victim.name} was eliminated! They were {victim.role}."
			await self.channel.send(f"> {message}")
			self.turns.broadcast(message)
		else:
			message = "No one was eliminated."
			await self.channel.send(message)
			self.turns.broadcast(message)

	async def mafia_choose_target(self):
		"""Run the mafia night discussion and kill vote.

		Switches the TurnManager to the mafia private thread, lets mafia
		players discuss (one round per mafia member), then runs a vote.
		If the vote is inconclusive, a random non-mafia target is chosen.

		Side effects:
			Sets self.night_actions['mafia_kill'] to the chosen target.
			Restores TurnManager to the main channel and full player list.
		"""
		alive = self.get_alive_players()
		mafia = [p for p in alive if p.role == MAFIA]

		self.turns.set_channel(self.mafia_chat)
		self.turns.set_participants(mafia)

		mafia_names = [p.name for p in mafia]
		self.turns.broadcast(f"You are part of the Mafia! Your team consists of: {', '.join(mafia_names)}. Choose wisely who to eliminate.")

		await self.turns.run_round(rounds=len(mafia))

		targets = [p for p in alive if p.role != MAFIA]
		kill = await self.turns.run_vote(
			candidates=targets,
			message=f"Night {self.day_number}: Mafia, choose a kill target.",
			placeholder="Choose a target...",
			emoji="🔪",
			break_ties_random=True,
		)

		if not kill and targets:
			import random
			kill = random.choice(targets)

		self.night_actions["mafia_kill"] = kill
		self.turns.set_channel(self.channel)
		self.turns.set_participants(alive)

	async def discussion_phase(self):
		"""Set up a TurnManager if needed and use it to run the discussion."""

		alive = self.get_alive_players()
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

		alive_names = [p.name for p in alive]
		self.turns.broadcast(f"Day {self.day_number} has begun. Alive players: {', '.join(alive_names)}. It's discussion time. Pay close attention to what others say and how they behave - look for suspicious activity or patterns.")

		await self.channel.send(f"**Day {self.day_number} begins...**")
		await self.turns.run_round(analyse=True)

	async def voting_phase(self):
		"""Kick off the voting phase and handle its results.

		The vote itself is mostly handled by TurnManager, which must
		already be initialized.

		Returns:
			The eliminated Player, or None if the vote was inconclusive.
		"""
		alive = self.get_alive_players()
		self.turns.set_participants(alive)

		victim = await self.turns.run_vote(
			candidates=alive,
			message=f"Day {self.day_number}: Vote to eliminate a player.",
			placeholder="Vote for a player...",
			emoji="🗳️",
			allow_abstain=True,
			require_majority=True
		)

		if victim:
			# run_day_phase also sets this.
			victim.alive = False
			victim.death_reason = "lynch"
			message = f"{victim.name} was voted out and eliminated. They were {victim.role}."
			self.turns.broadcast(message)
		else:
			message = "Nobody was voted out today. The vote was inconclusive or everyone abstained."
			self.turns.broadcast(message)

		return victim
