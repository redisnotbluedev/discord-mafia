"""Game scheduling, role assignment, and lifecycle management.

Contains MafiaSheduler which manages the pre-game lobby countdown, role
distribution, Discord permission setup, and the overall game lifecycle.
"""

from typing import TypedDict

from classes.roles import Alignment, TOWN, MAFIA
from classes.player import Player, AIAbstraction
from classes.views import JoinGameView
import asyncio, time, discord, random, data, logging, traceback

logger = logging.getLogger(__name__)

class MafiaSchedulerConfig(TypedDict):
	mafia: int
	town: int
	role_Doctor: bool
	role_Sheriff: bool
	role_Vigilante: bool
	role_Jester: bool

class MafiaSheduler:
	"""Orchestrates game setup, role assignment, and the game lifecycle.

	Created by JoinGameView when a player clicks Play.  Manages:
	- Pre-game countdown with automatic retry (up to 3 attempts)
	- Role distribution based on the settings config
	- Discord permission lockdown during the game
	- Game execution (delegates to MafiaGame.run())
	- Post-game cleanup (role removal, permission restoration, thread locking)
	"""

	def __init__(self, abstractor, lobby: JoinGameView, message: discord.Message):
		"""Initialize the scheduler with default role distribution.

		Sets up the initial mafia/town split (~1/3 mafia) and creates
		a MafiaGame instance.  The config dict is shared with SettingsView
		so settings changes are reflected here.

		Args:
			abstractor: The GameAbstractor for this channel.
			lobby: The Lobby for this channel.
			message: A Discord message from JoinGameView (I'm not clear on where _this_ comes from)
		"""
		from classes.game import MafiaGame
		self.abstractor = abstractor
		self.lobby: JoinGameView = lobby
		self.message: discord.Message = message
		self.start_job: asyncio.Task | None = None
		self.attempts = 0
		total_players = len(self.abstractor.players)
		mafia = max(1, total_players // 3)
		town = max(mafia + 1, total_players - mafia)
		self.config: MafiaSchedulerConfig = {
			"mafia": mafia,
			"town": town,
			"role_Doctor": True,
			"role_Sheriff": True,
			"role_Vigilante": False,
			"role_Jester": False,
		}
		self.game = MafiaGame(abstractor, self, self.config)
		self.abstractor.game = self.game

	def schedule(self, start_at: int | float):
		"""Schedule the game to start at a given Unix timestamp.

		Creates an asyncio task that sleeps until start_at, then calls
		start_game().  If there aren't enough players, retries up to 3
		times with a 5-minute delay.  After 3 failures, cancels the game.

		Args:
			start_at: Unix timestamp when the game should start.
		"""
		async def task():
			await asyncio.sleep(start_at - time.time())
			if not await self.start_game():
				self.attempts += 1
				if self.attempts >= 3:
					await self.message.channel.send("Not enough players to start the game!\nPlease restart with more players.")
					await self.message.delete()
					self.abstractor.running = False
					data.update_game_status(self.abstractor.bot)
					await self.abstractor.on_message(True) # God idek what this does but I implemented it so I should know...
					# Oh it cancels it and then sends a ghost message to move the lobby down
					return

				await self.message.channel.send("Not enough players to start the game!")
				self.lobby.start_at = int(time.time()) + 60 * 5
				await self.message.edit(embed=self.lobby.generate_embed())
				self.schedule(self.lobby.start_at)

		new_task = asyncio.create_task(task())
		self.start_job = new_task

	async def start_game(self):
		"""Set up permissions, assign roles, run the game, and clean up.

		This is the main game lifecycle method.  It:
		1. Locks the channel (disables @everyone from sending messages)
		2. Grants the bot necessary permissions
		3. Assigns the 'Mafia Player' Discord role
		4. DMs each human player their role
		5. Creates the Mafia private thread
		6. Runs the game via MafiaGame.run()
		7. Announces the winner and reveals all roles
		8. Cleans up (unlock channel, remove roles, lock thread)

		Returns:
			True if the game ran (regardless of errors), False if there
			weren't enough players (< 5) to start.
		"""
		if len(self.abstractor.players) < 5: return False
		mafia_chat: discord.Thread | None = None
		player_role: discord.Role | None = None
		original_overwrites = None

		config = data.load()
		maybe_channel = self.message.channel
		assert isinstance(maybe_channel, discord.TextChannel)  # PYREX NOTE: TEXTUAL_CHANNEL is not specific enough; Thread doesn't have overwrites_for
		channel: discord.TextChannel = maybe_channel
		guild = self.message.guild
		assert guild is not None

		try:
			self.game.config = self.config
			await self.message.edit(view=None, embed=self.lobby.generate_embed(show_starting_soon=False))

			await channel.send("Starting game...")

			self.setup_roles()
			player_role = guild.get_role(config["guilds"][str(guild.id)]["player_role"])
			assert player_role is not None

			original_overwrites = channel.overwrites_for(guild.default_role)

			# Use PermissionOverwrite to ensure the bot keeps necessary permissions
			# while restricting the @everyone role.
			await channel.set_permissions(
				guild.me,
				overwrite=discord.PermissionOverwrite(
					view_channel=True,
					send_messages=True,
					create_public_threads=True,
					create_private_threads=True,
					manage_threads=True,
					send_messages_in_threads=True
				)
			)

			await channel.set_permissions(
				guild.default_role,
				overwrite=discord.PermissionOverwrite(
					send_messages=False,
					send_messages_in_threads=False,
					create_private_threads=False,
					create_public_threads=False,
					add_reactions=False,
					use_application_commands=False
				)
			)

			for player in self.game.players:
				user = player.user
				if isinstance(user, discord.Member):
					await user.add_roles(player_role)

					i = self.abstractor.interactions.get(user.id)
					if i:
						await i.followup.send(f"""
							You are {player.role.describe()}
						""", ephemeral=True)
				elif not isinstance(user, AIAbstraction):
					# hmmmm
					logger.warning(f"User is of type {type(user)}?!?!?!?!?!??!?! What is this?!?!?!??!?!?!")

			mafia_chat = await channel.create_thread(name="Mafia Private Chat", invitable=False)
			self.game.mafia_chat = mafia_chat
			self.game.channel = channel

			for player in self.game.players:
				if player.role == MAFIA and isinstance(player.user, discord.abc.User):
					await mafia_chat.add_user(player.user)

			await mafia_chat.send(embed=discord.Embed(
				colour=discord.Colour.red(),
				title="Mafia Private Chat",
				description="Mafia Players:\n" + "\n".join([f"- {p.name}" for p in self.game.players if p.role == MAFIA])
			))

			winner = await self.game.run()
			await channel.send(f"# 🎉 {winner} wins! 🎉\n-# Thanks for playing!")
			roles = discord.Embed(
				colour=discord.Colour.blurple(),
				title="Roles"
			)

			for alignment in Alignment:
				aligned_players = [f"{p.role.emoji} {p.name}: {p.role}" for p in self.game.players if p.role.alignment == alignment]
				if aligned_players:
					roles.add_field(name=alignment.value, value="\n".join(aligned_players), inline=False)

			await channel.send(embed=roles)

		except Exception:
			error = traceback.format_exc()
			try:
				await self.message.channel.send(f"An error occured during the game:\n```python\n{error}\n```\n-# If this error continues, please contact a developer.")
			except (discord.errors.HTTPException, RuntimeError):
				logger.error(f"Failed to send error message: {error}")

		finally:
			try:
				if mafia_chat:
					await mafia_chat.edit(locked=True)
			except (discord.errors.HTTPException, RuntimeError):
				# Session might be closed during shutdown or thread doesn't exist
				logger.warn("Could not lock mafia chat thread during cleanup")

			self.abstractor.reset()
			self.abstractor.running = False
			data.update_game_status(self.abstractor.bot)

			tasks = []
			for player in self.game.players:
				user = player.user
				if isinstance(user, discord.Member):
					assert player_role is not None
					tasks.append(user.remove_roles(player_role))

			if original_overwrites is not None:
				if original_overwrites.is_empty():
					tasks.append(channel.set_permissions(guild.default_role, overwrite=None))
				else:
					tasks.append(channel.set_permissions(guild.default_role, overwrite=original_overwrites))

			try:
				await asyncio.gather(*tasks)
			except (discord.errors.HTTPException, RuntimeError):
				# Session might be closed during shutdown
				logger.warn("Could not remove player roles during cleanup")

			await self.abstractor.on_message(True)

			return True

	def setup_roles(self):
		"""Shuffle players and assign roles based on the config.

		Adjusts mafia/town counts if they don't sum to total_players.
		Players are shuffled before assignment for random distribution.

		Side effects:
			Populates self.game.players with new Player instances
			(copies of the lobby players with roles assigned).
			The `self.game.players` list is *not* cleared before the new
			players are appended.
		"""
		from classes.roles import ALL_ROLES
		total_players = len(self.abstractor.players)
		mafia = self.config.get("mafia", max(1, total_players // 3))
		town = self.config.get("town", max(mafia + 1, total_players - mafia))

		if mafia + town > total_players:
			mafia = min(mafia, (total_players - 1) // 2)
			town = total_players - mafia
		elif mafia + town < total_players:
			town += total_players - (mafia + town)
		self.config["mafia"] = mafia
		self.config["town"] = town
		players = list(self.abstractor.players.values())
		random.shuffle(players)

		players_rolled = 0

		enabled_roles = [role for role in ALL_ROLES if self.config.get(f"role_{role.name}", False)]

		neutral_roles = [r for r in enabled_roles if r.alignment == Alignment.NEUTRAL]
		special_town_roles = [r for r in enabled_roles if r.is_special() and r.alignment == Alignment.TOWN]

		assigned_special = len(neutral_roles) + len(special_town_roles)
		available_for_town = max(0, total_players - mafia - assigned_special)
		town_count = min(town - len(special_town_roles), available_for_town)

		for role in neutral_roles:
			if players_rolled >= total_players:
				break
			user = players[players_rolled]
			player = Player(user.user)
			player.role = role
			self.game.players.append(player)
			players_rolled += 1

		for role in special_town_roles:
			if players_rolled >= total_players:
				break
			user = players[players_rolled]
			player = Player(user.user)
			player.role = role
			self.game.players.append(player)
			players_rolled += 1

		for _ in range(town_count):
			if players_rolled >= total_players:
				break
			user = players[players_rolled]
			player = Player(user.user)
			player.role = TOWN
			self.game.players.append(player)
			players_rolled += 1

		for _ in range(min(mafia, total_players - players_rolled)):
			user = players[players_rolled]
			player = Player(user.user)
			player.role = MAFIA
			self.game.players.append(player)
			players_rolled += 1

		logger.info(f"Initialised roles with {len(self.game.players)} players.")
