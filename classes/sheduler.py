from classes.abstractor import GameAbstractor
from classes.game import MafiaGame
from classes.player import Player, Role
import asyncio, time, discord, random, data, logging, traceback

logger = logging.getLogger(__name__)

class MafiaSheduler:
	def __init__(self, abstractor: GameAbstractor):
		from classes.views import JoinGameView

		self.abstractor = abstractor
		self.lobby: JoinGameView = None
		self.message: discord.Message = None
		self.start_job: asyncio.Task = None
		self.attempts = 0
		self.game = MafiaGame(abstractor)
		self.config = {}

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
		try:
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

			mafia_chat = await channel.create_thread(name="Mafia Private Chat", invitable=False)
			self.game.mafia_chat = mafia_chat
			self.game.channel = channel

			for player in self.game.players:
				if player.role == Role.MAFIA and isinstance(player.user, discord.abc.User):
					await mafia_chat.add_user(player.user)

			await channel.set_permissions(
				guild.default_role,
				send_messages=False,
				add_reactions=False,
				create_public_threads=False,
				create_private_threads=False
			)

			winner = await self.game.run()
			await channel.send(f"# 🎉 {winner} wins! 🎉\n-# Thanks for playing!")

		except Exception:
			error = traceback.format_exc()
			await self.message.channel.send(f"Unable to start game; an error occured:\n```python\n{error}\n```\n-# If this error continues, please contact a developer.")

		finally:
			if channel:
				await channel.set_permissions(
					guild.default_role,
					send_messages=None,
					add_reactions=None,
					create_public_threads=None,
					create_private_threads=None
				)
			if mafia_chat:
				await mafia_chat.edit(locked=True)

			self.abstractor.running = False

			return True

	def setup_roles(self):
		total_players = len(self.abstractor.players)
		mafia = self.config.setdefault("mafia", max(1, min(total_players // 3, total_players - 3)))
		town = self.config.setdefault("town", total_players - mafia)
		players = list(self.abstractor.players.values())
		random.shuffle(players)

		players_rolled = 0

		for _ in range(town - 2):
			user = players[players_rolled]
			player = Player(user.user)
			player.role = Role.TOWN

			self.game.players.append(player)
			players_rolled += 1

		doctor = Player(players[players_rolled].user)
		doctor.role = Role.DOCTOR
		self.game.players.append(doctor)
		players_rolled += 1

		sheriff = Player(players[players_rolled].user)
		sheriff.role = Role.SHERIFF
		self.game.players.append(sheriff)
		players_rolled += 1

		for _ in range(mafia):
			user = players[players_rolled]
			player = Player(user.user)
			player.role = Role.MAFIA

			self.game.players.append(player)
			players_rolled += 1

		log = []
		for player in self.game.players:
			log.append(f"{player.role} - {player.name}")
		logger.info("\n".join(log))
