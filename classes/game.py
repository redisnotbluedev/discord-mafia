from classes.abstractor import GameAbstractor
from classes.player import Player, Role
import asyncio, time, discord, random, data, logging

logger = logging.getLogger(__name__)

class MafiaGame:
	def __init__(self, abstractor: GameAbstractor):
		from classes.views import JoinGameView

		self.abstractor = abstractor
		self.lobby: JoinGameView = None
		self.message: discord.Message = None
		self.start_job: asyncio.Task = None
		self.attempts = 0
		self.players = []
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
					await self.abstractor.on_message(True)
					return

				await self.message.channel.send("Not enough players to start the game!")
				self.lobby.start_at = int(time.time()) + 60 * 5
				await self.message.edit(embed=self.lobby.generate_embed())
				self.schedule(self.lobby.start_at)
		
		new_task = asyncio.create_task(task())
		self.start_job = new_task

	async def start_game(self):
		if len(self.abstractor.players) < 5: return False
		bot = self.abstractor.bot
		await self.message.edit(view=None)
		
		self.setup_roles()
		config = data.load()
		channel = self.message.channel
		guild = self.message.guild

		for player in self.players:
			user = player.user
			if isinstance(user, discord.Member):
				print(config)
				await user.add_roles(self.message.guild.get_role(
					config["guilds"][str(guild.id)]["player_role"]
				))
			else:
				pass

		await channel.send("Starting game...")
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

			self.players.append(player)
			players_rolled += 1
		
		doctor = Player(players[players_rolled].user)
		doctor.role = Role.DOCTOR
		self.players.append(doctor)
		players_rolled += 1

		sheriff = Player(players[players_rolled].user)
		sheriff.role = Role.SHERIFF
		self.players.append(sheriff)
		players_rolled += 1

		for _ in range(mafia):
			user = players[players_rolled]
			player = Player(user.user)
			player.role = Role.MAFIA

			self.players.append(player)
			players_rolled += 1