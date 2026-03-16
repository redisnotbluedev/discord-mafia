# https://discord.com/oauth2/authorize?client_id=1457229259243257947&permissions=361582569472&integration_type=0&scope=bot+applications.commands

"""Bot entry point.

Loads environment variables, creates the Discord bot client, registers
cogs, and starts the event loop.  On ready, creates a GameAbstractor
for each previously configured channel and posts a fresh lobby embed.
"""

import discord, os, logging, data, asyncio, traceback
from discord.ext import commands
from dotenv import load_dotenv

from classes.abstractor import GameAbstractor
from logging_utils import WebhookLoggingHandler

load_dotenv()

config = data.load()

intents = discord.Intents.default()
intents.message_content = True

class BotWithAbstractors(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix="", intents=intents)
		self.abstractors: list[GameAbstractor] = []

bot = BotWithAbstractors()
logger = logging.getLogger(__name__)

bot.abstractors = []

@bot.event
async def on_ready():
	"""Initialize game abstractors and logging after the bot connects."""
	log_webhook_url = os.getenv("LOG_WEBHOOK_URL")
	if log_webhook_url:
		log_webhook = discord.Webhook.from_url(log_webhook_url, client=bot)
		webhook_handler = WebhookLoggingHandler(log_webhook, level=logging.INFO)
		logging.getLogger().addHandler(webhook_handler)
		logger.info("Global webhook logging enabled")

	logger.info(f"Logged in as {bot.user}!")

	profiles = config.get("profiles", {})
	tasks = []
	for channel in profiles:
		abstractor = GameAbstractor(int(channel), bot)
		tasks.append(abstractor.on_message(True)) # Force a lobby refresh since the button's stale (from last session)
		bot.abstractors.append(abstractor)
	await asyncio.gather(*tasks)
	logger.info("Loading game abstractors, total %i", len(bot.abstractors))
	data.update_game_status(bot)

@bot.event
async def setup_hook():
	"""Register cogs and sync slash commands on bot startup."""
	from cogs.moderation import ModerationCog
	from cogs.info import InfoCog
	from cogs.games import GamesCog

	await bot.add_cog(ModerationCog(bot))
	await bot.add_cog(InfoCog(bot))
	await bot.add_cog(GamesCog(bot))

	synced_global = await bot.tree.sync()
	logger.info("Commands synced globally: %s", [c.name for c in synced_global])

@bot.event
async def on_message(message: discord.Message):
	"""Route incoming messages to game abstractors.
	
	Also implements a debugging hook.
	"""
	if message.author == bot.user:
		return

	if message.content.startswith("!eval") and message.author.id == 1337909802931716197:
		code = message.content[6:].strip()
		try:
			abstractor = None
			for abs in bot.abstractors:
				if abs.channel == message.channel.id:
					abstractor = abs
					break
			wrapped_code = "async def _eval(bot, message, discord, asyncio, __import__, abstractor):\n" + "\n".join(f"    {line}" for line in code.split("\n")) + "\n    return None"
			globals_dict = {}
			exec(wrapped_code, globals_dict)
			result = await globals_dict["_eval"](bot, message, discord, asyncio, __import__, abstractor)
			await message.channel.send(f"Result: {result}")
		except Exception:
			await message.channel.send(f"Error:\n```python\n{traceback.format_exc()}\n```")
		return

	for abstractor in bot.abstractors:
		await abstractor.on_message(message)

if __name__ == "__main__":
	TOKEN = os.getenv("TOKEN")
	assert TOKEN is not None
	bot.run(TOKEN, root_logger=True)
