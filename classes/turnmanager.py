from classes.player import Player, AIAbstraction
from classes.views import VoteView
import discord, openai, random, queue, logging, data

logger = logging.getLogger(__name__)

class TurnManager:
	def __init__(self, participants: list[Player], channel: discord.abc.MessageableChannel, bot: discord.Client, client: openai.OpenAI = None):
		self.participants = participants
		self.channel = channel
		self.client = client or openai.OpenAI()
		config = data.load()
		self.bot = bot
		self.webhook: discord.Webhook = discord.Webhook.from_url(
			# If this doesn't exist, screw you
			config.profiles[str(self.channel.id)].webhook,
			client=bot
		)

		self.running = False
		self.message_queue = queue.Queue()
		self.required_author = -1
		self.context: dict[AIAbstraction, list] = {} # player -> openai messages

	def broadcast(self, text, exclude: Player = None):
		for player in self.participants:
			if player != exclude and isinstance(player.user, AIAbstraction):
				self.context[player.user].append({"role": "user", "content": text})

	async def run_round(self):
		self.running = True
		random.shuffle(self.participants)
		for player in self.participants:
			if isinstance(player.user, discord.Member):
				self.channel.set_permissions(
					player.user,
					send_messages=True
				)

				self.required_author = player.user.id
				logger.info("Waiting for message send")
				message = self.message_queue.get()
				self.required_author = -1
				self.broadcast(f"{player.name} said: {message.content}")

			elif isinstance(player.user, AIAbstraction):
				response = self.client.chat.completions.create(
					model=player.user.model,
					messages=self.context[player.user]
				)
				text = response.choices[0].message.content
				await self.webhook.send(
					username=player.name,
					avatar_url=player.user.avatar,
					content=text
				)
				self.broadcast(f"{player.name} said: {text}", player)

	async def run_vote(self, candidates: list[Player], message, placeholder="Vote for a player...", emoji="🗳️"):
		poll = await self.mafia_chat.send(message + "\nVotes:\nNo votes yet.", view=VoteView(
			players=[p.name for p in candidates],
			placeholder=placeholder,
			emoji=emoji
		))
		for player in self.participants:
			if isinstance(player.user, AIAbstraction):
				serialised_targets = []
				for player in candidates:
					serialised_targets.append(player.name)

				messages = self.context[player.user]
				messages.append({"role": "user", "content": f"{message}\nOptions:\n{"\n".join(serialised_targets)}"})

				self.client.chat.completions.create(
					model=player.user.model,
					messages=messages
				)

	def on_message(self, message: discord.Message):
		if message.author.id == self.required_author and message.content:
			self.message_queue.put(message)
