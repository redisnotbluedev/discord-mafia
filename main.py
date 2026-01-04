import discord, os, logging
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 
bot = discord.Client(intents=intents)
logger = logging.getLogger(__name__)

class StartGameView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=300)

	@discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
	async def run_cmd(self, interaction: discord.Interaction, button: discord.ui.Button):
		await interaction.response.send_message("Starting game...")

@bot.event
async def on_ready():
	logger.info("hello world")

@bot.event
async def on_message(message: discord.Message):
	if message.author == bot.user:
		return

	embed: discord.Embed = discord.Embed(
		title="AI Plays Mafia",
		description="The series by Turing Games, now as a Discord bot!",
		color=discord.Color.blurple()
	)
	await message.channel.send(embed=embed, view=StartGameView())

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN, root_logger=True)
