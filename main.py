import discord, os, logging
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
	pass

@bot.event
async def on_message(message):
	if message.author == bot.user:
		return

	if message.content.startswith("$hello"):
		await message.channel.send("Hello!")

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
