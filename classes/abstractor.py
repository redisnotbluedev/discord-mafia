import discord, logging, data, asyncio

from discord.ext import commands
from classes.player import Player
from classes.game import MafiaGame
logger = logging.getLogger(__name__)

class GameAbstractor:
	def __init__(self, channel: int, bot: commands.Bot):
		self.channel = channel
		self.channel_key = str(channel)
		self.bot = bot
		self.players: dict[int, Player] = {}  # user_id -> Player
		self.running: bool = False
		self.owner: discord.User = None
		self.interactions: dict[int, discord.Interaction] = {}
		config = data.load()
		self.last_lobby_id: int | None = config.get("profiles", {}).get(self.channel_key, {}).get("last_lobby")
		# `lobby_active` reflects only in-process state; do not derive it from persisted `last_lobby_id`
		self.lobby_active: bool = False
		self.game: MafiaGame = None

	async def _delete_last_lobby(self) -> None:
		if not self.last_lobby_id:
			return

		channel = self.bot.get_channel(self.channel)
		if not channel:
			logger.warning("Channel %s not found to delete last lobby", self.channel)
			return

		try:
			msg = await channel.fetch_message(self.last_lobby_id)
			await msg.delete()
		except discord.NotFound:
			logger.info("Last lobby message %s already gone", self.last_lobby_id)
		except discord.Forbidden:
			logger.warning("Missing permissions to delete message %s", self.last_lobby_id)
		except discord.HTTPException as exc:
			logger.error("Failed to delete message %s: %s", self.last_lobby_id, exc)

	async def on_message(self, message: discord.Message | bool):
		if isinstance(message, discord.Message):
			# Accept message if it's in the main channel OR in the mafia chat
			is_in_main_channel = message.channel.id == self.channel
			is_in_mafia_chat = self.game and self.game.mafia_chat and message.channel.id == self.game.mafia_chat.id
			if not (is_in_main_channel or is_in_mafia_chat):
				return
		elif not message:
			return

		logger.debug(f"Received a message, running: {self.running}")
		if self.running or self.lobby_active:
			if self.game:
				await self.game.turns.on_message(message)
			return

		from classes.views import StartGameView

		self.lobby_active = True
		new_msg = await asyncio.gather(
			message.channel.send(
				embed=discord.Embed(
					title="AI Plays Mafia",
					description="The series by Turing Games, now as a Discord bot!",
					color=discord.Color.blurple(),
				),
				view=StartGameView(self),
			),
			self._delete_last_lobby()
		)

		self.last_lobby_id = new_msg[0].id
		self.save_config()

	def save_config(self):
		config = data.load()
		config.setdefault("profiles", {}).setdefault(self.channel_key, {})["last_lobby"] = self.last_lobby_id
		data.save(config)
