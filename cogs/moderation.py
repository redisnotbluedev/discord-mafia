from discord.ext import commands
from discord import app_commands
import discord

class ModerationCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

