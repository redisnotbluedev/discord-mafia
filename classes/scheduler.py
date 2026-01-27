from typing import TYPE_CHECKING
from classes.game import MafiaGame
from classes.roles import Alignment, TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE
from classes.player import Player, AIAbstraction
from classes.views import JoinGameView
import asyncio, time, discord, random, data, logging, traceback

if TYPE_CHECKING:
	from classes.abstractor import GameAbstractor

logger = logging.getLogger(__name__)

class MafiaSheduler:
	def __init__(self, abstractor):
		self.abstractor: "GameAbstractor" = abstractor
		self.lobby: JoinGameView = None
		self.message: discord.Message = None
		self.start_job: asyncio.Task = None
		self.attempts = 0
		self.game = MafiaGame(abstractor)
		self.config = {
			"mafia": 1,
			"town": 4,
			"role_Doctor": True,
			"role_Sheriff": True,
			"role_Vigilante": False,
			"role_Jester": False,
		}
		self.game.config = self.config

	def schedule(self, start_at: int):
		async def task():
			await asyncio.sleep(start_at - time.time())
			if not await self.start_game():
				self.attempts += 1
				if self.attempts >= 3:
					await self.message.channel.send("Not enough players to start the game!\nPlease restart with more players.")
					await self.message.delete()
					self.abstractor.running = True
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
		if len(self.abstractor.players) < 5: return False
		mafia_chat = None
		try:
			self.game.config = self.config

			self.abstractor.game = self.game
			await self.message.edit(view=None)

			config = data.load()
			channel = self.message.channel
			guild = self.message.guild

			await channel.send("Starting game...")

			self.setup_roles()
			player_role = guild.get_role(config["guilds"][str(guild.id)]["player_role"])

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
					logger.warn(f"User is of type {user.type}!!")

			mafia_chat = await channel.create_thread(name="Mafia Private Chat", invitable=False)
			self.game.mafia_chat = mafia_chat
			self.game.channel = channel

			for player in self.game.players:
				if player.role == MAFIA and isinstance(player.user, discord.abc.User):
					await mafia_chat.add_user(player.user)

			winner = await self.game.run()
			await channel.send(f"# 🎉 {winner} wins! 🎉\n-# Thanks for playing!")

		except Exception:
			error = traceback.format_exc()
			try:
				await self.message.channel.send(f"Unable to start game; an error occured:\n```python\n{error}\n```\n-# If this error continues, please contact a developer.")
			except (discord.errors.HTTPException, RuntimeError):
				logger.error(f"Failed to send error message: {error}")

		finally:
			try:
				if mafia_chat:
					await mafia_chat.edit(locked=True)
			except (discord.errors.HTTPException, RuntimeError):
				# Session might be closed during shutdown or thread doesn't exist
				logger.debug("Could not lock mafia chat thread during cleanup")

			self.abstractor.reset()
			self.abstractor.running = False

			tasks = []
			for player in self.game.players:
				user = player.user
				if isinstance(user, discord.Member):
					tasks.append(user.remove_roles(player_role))

			try:
				await asyncio.gather(*tasks)
			except (discord.errors.HTTPException, RuntimeError):
				# Session might be closed during shutdown
				logger.debug("Could not remove player roles during cleanup")

			return True

	def setup_roles(self):
		from classes.roles import ALL_ROLES
		total_players = len(self.abstractor.players)
		mafia = self.config.get("mafia", max(1, min(total_players // 3, total_players - 3)))
		town = self.config.get("town", total_players - mafia)
		# Adjust town if counts don't match total players
		if mafia + town > total_players:
			town = max(1, total_players - mafia)
		elif mafia + town < total_players:
			town += total_players - (mafia + town)
		self.config["mafia"] = mafia
		self.config["town"] = town
		players = list(self.abstractor.players.values())
		random.shuffle(players)

		players_rolled = 0

		# Get enabled roles
		enabled_roles = [role for role in ALL_ROLES if self.config.get(f"role_{role.name}", False)]

		# Separate by alignment
		neutral_roles = [r for r in enabled_roles if r.alignment == Alignment.NEUTRAL]
		special_town_roles = [r for r in enabled_roles if r.is_special() and r.alignment == Alignment.TOWN]

		# Calculate available slots for town (regular town)
		assigned_special = len(neutral_roles) + len(special_town_roles)
		available_for_town = max(0, total_players - mafia - assigned_special)
		town_count = min(town - len(special_town_roles), available_for_town)

		# Assign neutral roles
		for role in neutral_roles:
			if players_rolled >= total_players:
				break
			user = players[players_rolled]
			player = Player(user.user)
			player.role = role
			self.game.players.append(player)
			players_rolled += 1

		# Assign special town roles
		for role in special_town_roles:
			if players_rolled >= total_players:
				break
			user = players[players_rolled]
			player = Player(user.user)
			player.role = role
			self.game.players.append(player)
			players_rolled += 1

		# Assign town roles
		for _ in range(town_count):
			if players_rolled >= total_players:
				break
			user = players[players_rolled]
			player = Player(user.user)
			player.role = TOWN
			self.game.players.append(player)
			players_rolled += 1

		# Assign mafia roles
		for _ in range(min(mafia, total_players - players_rolled)):
			user = players[players_rolled]
			player = Player(user.user)
			player.role = MAFIA
			self.game.players.append(player)
			players_rolled += 1

		log = []
		for player in self.game.players:
			log.append(f"{player.role} - {player.name}")
		logger.info("\n".join(log))
