import discord, os, logging, data
from classes.abstractor import GameAbstractor
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 
bot = discord.Client(intents=intents)
logger = logging.getLogger(__name__)

config = {}
abstractors: list[GameAbstractor] = []

@bot.event
async def on_ready():
	logger.info(f"Logged in as {bot.user}!")

@bot.event
async def on_message(message: discord.Message):
	if message.author == bot.user:
		return

	for abstractor in abstractors:
		abstractor.on_message(message)

if __name__ == "__main__":
	config = data.load()
	for channel in config.channels:
		abstractors.append(GameAbstractor(channel))
	
	TOKEN = os.getenv("TOKEN")
	bot.run(TOKEN, root_logger=True)
