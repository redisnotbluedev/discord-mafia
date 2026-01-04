import discord, os, logging
from classes.views import StartGameView
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 
bot = discord.Client(intents=intents)
logger = logging.getLogger(__name__)

players = []

@bot.event
async def on_ready():
	logger.info(f"Logged in as {bot.user}!")

@bot.event
async def on_message(message: discord.Message):
	if message.author == bot.user:
		return
	
	await message.channel.send(embed=discord.Embed(
		title="AI Plays Mafia",
		description="The series by Turing Games, now as a Discord bot!",
		color=discord.Color.blurple()
	), view=StartGameView(players))

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN, root_logger=True)
