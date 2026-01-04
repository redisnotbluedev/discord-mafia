import discord, os, logging, data
from discord.ext import commands
from dotenv import load_dotenv

from classes.abstractor import GameAbstractor
from cogs.moderation import ModerationCog
from cogs.info import InfoCog

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="", intents=intents)
logger = logging.getLogger(__name__)

config = {}
abstractors: list[GameAbstractor] = []

@bot.event
async def on_ready():
	logger.info(f"Logged in as {bot.user}!")

@bot.event
async def setup_hook():
	await bot.add_cog(ModerationCog(bot))
	await bot.add_cog(InfoCog(bot))
	
	await bot.tree.sync()
	logger.info("Synced all bot commands!")

@bot.event
async def on_message(message: discord.Message):
	if message.author == bot.user:
		return

	for abstractor in abstractors:
		abstractor.on_message(message)

if __name__ == "__main__":
	config = data.load()
	for channel in config.get("channels", []):
		abstractors.append(GameAbstractor(channel))
	
	TOKEN = os.getenv("TOKEN")
	bot.run(TOKEN, root_logger=True)
