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

bot.abstractors = []

@bot.event
async def on_ready():
	logger.info(f"Logged in as {bot.user}!")

@bot.event
async def setup_hook():
	await bot.add_cog(ModerationCog(bot))
	await bot.add_cog(InfoCog(bot))

	profiles = data.load().get("profiles", {})
	for channel in profiles:
		bot.abstractors.append(GameAbstractor(int(channel), bot))
	logger.info("Loading game abstractors, total %i", len(bot.abstractors))

	await bot.tree.sync()
	logger.info("Synced all bot commands!")

@bot.event
async def on_message(message: discord.Message):
	if message.author == bot.user:
		return

	for abstractor in bot.abstractors:
		await abstractor.on_message(message)

if __name__ == "__main__":	
	TOKEN = os.getenv("TOKEN")
	bot.run(TOKEN, root_logger=True)
