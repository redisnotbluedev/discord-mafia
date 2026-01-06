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
			permissions = interaction.channel.permissions_for(interaction.guild.me)
			if permissions.manage_roles:
				await interaction.response.send_message("The bot needs the `Manage Roles` permission to set up private chats.")
				return
			if permissions.manage_webhooks:
				await interaction.response.send_message("The bot needs the `Manage Webhooks` permission to set up AI messages.")
				return

			channel = interaction.channel
			config = data.load()
			
			if str(channel.id) in config.get("profiles", {}):
				await interaction.response.send_message(f"The game is already set up in <#{channel.id}>.", ephemeral=True)
				return
			
			webhook: discord.Webhook = await channel.create_webhook(name="AI Plays Mafia", reason="Required for sending AI messages")
			config.setdefault("profiles", {})[channel.id] = {"webhook": webhook.url}

			if not str(interaction.guild.id) in config.get("guilds", {}):
				player = await interaction.guild.create_role(name="Mafia Player")
				config.setdefault("guilds", {})[channel.id] = {"player_role": player.id}

			self.bot.abstractors.append(GameAbstractor(channel.id, self.bot))

			data.save(config)

			await interaction.response.send_message(f"Mafia game set up in <#{channel.id}>!", ephemeral=True)
		except Exception:
			e = traceback.format_exc()
			await interaction.response.send_message(f"Failed to set up game:\n```python\n{e}\n```")