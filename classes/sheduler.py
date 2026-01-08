from classes.abstractor import GameAbstractor
from classes.game import MafiaGame
from classes.player import Player, Role
import asyncio, time, discord, random, data, logging

logger = logging.getLogger(__name__)

class MafiaSheduler:
	def __init__(self, abstractor: GameAbstractor):
		from classes.views import JoinGameView

		self.abstractor = abstractor
		self.lobby: JoinGameView = None
		self.message: discord.Message = None
		self.start_job: asyncio.Task = None
		self.attempts = 0
		self.game = MafiaGame()
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
		await self.message.edit(view=None)
		
		self.setup_roles()
		config = data.load()
		channel = self.message.channel
		guild = self.message.guild
		player_role = guild.get_role(config["guilds"][str(guild.id)]["player_role"])

		for player in self.game.players:
			user = player.user
			if isinstance(user, discord.Member):
				await user.add_roles(player_role)
				
				i = self.abstractor.interactions.get(user.id)
				if i:
					i.followup.send("You are %s." % player.role, ephemeral=True)
		
		mafia_chat = await channel.create_thread(name="Mafia Private Chat", invitable=False)

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
		await channel.set_permissions(
			player_role,
			send_messages=True,
			add_reactions=True
		)

		await channel.send("Starting game...")

		async def send(text):
			await channel.send(text)
		
		async def send_mafia(text):
			await mafia_chat.send(text)

		self.game.send = send
		self.game.mafia_send = send_mafia
		await self.game.run()

		await channel.set_permissions(
			guild.default_role,
			send_messages=None,
			add_reactions=None,
			create_public_threads=None,
			create_private_threads=None
		)

		await mafia_chat.edit(archived=True)

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
			log.append(f"{player.role} - {player.user.name}")
		logger.info("\n".join(log))
	
	async def run(self):
		pass