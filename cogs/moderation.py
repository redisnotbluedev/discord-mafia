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

			if not permissions.send_messages:
				await interaction.response.send_message("The bot needs the `Send Messages` permission.")
				return
			if not permissions.send_messages_in_threads:
				await interaction.response.send_message("The bot needs the `Send Messages in Threads` permission.")
				return
			if not permissions.manage_roles:
				await interaction.response.send_message("The bot needs the `Manage Roles` permission to set up private chats.")
				return
			if not permissions.manage_webhooks:
				await interaction.response.send_message("The bot needs the `Manage Webhooks` permission to set up AI messages.")
				return
			if not permissions.create_private_threads:
				await interaction.response.send_message("The bot needs the `Create Private Threads` permission to create private chats.")
				return
			if not permissions.manage_messages:
				await interaction.response.send_message("The bot needs the `Manage Messages` permission to invite members to private chats.")
				return
			if not permissions.manage_threads:
				await interaction.response.send_message("The bot needs the `Manage Threads` to lock private chats.")
				return

			channel = interaction.channel
			config = data.load()

			if str(channel.id) in config.get("profiles", {}):
				await interaction.response.send_message(f"The game is already set up in <#{channel.id}>.", ephemeral=True)
				return

			if any(getattr(abstractor, "channel", None) == channel.id for abstractor in self.bot.abstractors):
				await interaction.response.send_message(f"The game is already set up in <#{channel.id}>.", ephemeral=True)
				return

			await channel.set_permissions(
				interaction.guild.me,
				send_messages=True,
				create_private_threads=True
			)

			webhook: discord.Webhook = await channel.create_webhook(name="AI Plays Mafia", reason="Required for sending AI messages")
			config.setdefault("profiles", {})[str(channel.id)] = {"webhook": webhook.url}

			if str(interaction.guild.id) not in config.get("guilds", {}):
				player = await interaction.guild.create_role(name="Mafia Player")
				await channel.set_permissions(
					player,
					send_messages=False,
					send_messages_in_threads=False,
					create_private_threads=False,
					create_public_threads=False,
					add_reactions=False,
					use_application_commands=False
				)
				config.setdefault("guilds", {})[interaction.guild.id] = {"player_role": player.id}
			else:
				player = await interaction.guild.get_role(config["guilds"][str(interaction.guild.id)]["player_role"])
				await channel.set_permissions(
					player,
					send_messages=False,
					send_messages_in_threads=False,
					create_private_threads=False,
					create_public_threads=False,
					add_reactions=False,
					use_application_commands=False
				)

			self.bot.abstractors.append(GameAbstractor(channel.id, self.bot))

			data.save(config)

			await interaction.response.send_message(f"Mafia game set up in <#{channel.id}>!", ephemeral=True)
		except Exception:
			e = traceback.format_exc()
			await interaction.response.send_message(f"Failed to set up game:\n```python\n{e}\n```")
