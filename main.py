import discord, os
from dotenv import load_dotenv

load_dotenv()

# Define intents
intents = discord.Intents.default()
# Enable the MESSAGE CONTENT intent for the bot to read message content
intents.message_content = True 

# Create an instance of a Client with specified intents
client = discord.Client(intents=intents)

@client.event
async def on_ready():
	"""Called when the bot has finished logging in and setting things up."""
	print(f"{client.user} has connected to Discord!")
	print("------")

@client.event
async def on_message(message):
	"""Called when a message is received."""
	if message.author == client.user:
		return

	if message.content.startswith("$hello"):
		await message.channel.send("Hello!")

TOKEN = os.getenv("TOKEN")
client.run(TOKEN)
