import discord, logging, data
from classes.views import StartGameView
from discord.ext import commands

logger = logging.getLogger(__name__)

class GameAbstractor:
	def __init__(self, channel: int, bot: commands.Bot):
		self.channel = channel
		self.channel_key = str(channel)
		self.bot = bot
		self.players: list[discord.User] = []
		self.running: bool = False

		config = data.load()
		self.last_lobby_id: int | None = config.get("last_lobbies", {}).get(self.channel_key)

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

	async def on_message(self, message: discord.Message):
		if message.channel.id != self.channel:
			return

		if self.running:
			logger.info("Skipping message send as the game is already running!")
			return

		await self._delete_last_lobby()

		new_msg = await message.channel.send(
			embed=discord.Embed(
				title="AI Plays Mafia",
				description="The series by Turing Games, now as a Discord bot!",
				color=discord.Color.blurple(),
			),
			view=StartGameView(self),
		)

		self.last_lobby_id = new_msg.id
		config = data.load()
		config.setdefault("last_lobbies", {})[self.channel_key] = self.last_lobby_id
		data.save(config)