from discord.ext import commands
from discord import app_commands
import discord, data, traceback

from classes.abstractor import GameAbstractor

class ModerationCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@app_commands.command(name="setup", description="Set up the bot in this channel.")
	async def setup(self, interaction: discord.Interaction):
		try:
			channel = interaction.channel
			config = data.load()
			
			if str(channel.id) in config.get("profiles", {}):
				await interaction.response.send_message(f"The game is already set up in <#{channel.id}>.", ephemeral=True)
				return
			
			webhook: discord.Webhook = await channel.create_webhook(name="AI Plays Mafia", reason="Required for sending AI messages")
			config.setdefault("profiles", {})[channel.id] = {"webhook": webhook.url}

			if not str(interaction.guild.id) in config.get("guilds", {}):
				pass

			self.bot.abstractors.append(GameAbstractor(channel, self.bot))

			data.save(config)

			await interaction.response.send_message(f"Mafia game set up in <#{channel.id}>!", ephemeral=True)
		except Exception:
			e = traceback.format_exc()
			await interaction.response.send_message(f"Failed to set up game:\n```python\n{e}\n```")