import discord, os, logging, asyncio
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 
bot = discord.Client(intents=intents)
logger = logging.getLogger(__name__)

players = []

class StartGameView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=300)

	@discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
	async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)
		#players.append(interaction.user)
		embed.add_field(name="Players", value="No players yet")#f"- {interaction.user.display_name or interaction.user.name}", inline=False)
		await interaction.response.edit_message(embed=embed, view=JoinGameView())

class JoinGameView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=300)

	@discord.ui.button(label="Join", style=discord.ButtonStyle.secondary)
	async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
		if interaction.user in players:
			await interaction.response.send_message("You're already in the game!", ephemeral=True)
			return

		embed: discord.Embed = discord.Embed(
			title="AI Plays Mafia",
			description="The series by Turing Games, now as a Discord bot!",
			color=discord.Color.green()
		)
		players.append(interaction.user)
		embed.add_field(name="Players", value="\n".join([f"- {u.display_name or u.name}" for u in players]))
		await interaction.response.edit_message(embed=embed)

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
	), view=StartGameView())

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN, root_logger=True)
