"""Admin/moderation slash commands (setup)."""

from discord.ext import commands
from discord import app_commands
import discord, data, traceback, os

from classes.abstractor import GameAbstractor

class ModerationCog(commands.Cog):
	"""Admin commands for bot configuration.

	Provides /setup, which:
	1. Checks required bot permissions
	2. Creates a webhook for AI player messages
	3. Creates a 'Mafia Player' role (once per guild)
	4. Registers a GameAbstractor for the channel
	"""

	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@app_commands.command(name="setup", description="Set up the bot in this channel.")
	async def setup(self, interaction: discord.Interaction):
		"""Installs the bot.
		
		If the user is not an admin, the bot does not have the permissions
		it needs to play the game, or the bot is already set up in the
		specified channel, this sends an error message instead of
		setting up the bot.

		If an operation throws an exception, the bot will send an error
		message to the channel and stop. Setup may be partially complete.

		When setup completes, data and game state files are updated.
		"""
		if str(interaction.user.id) not in os.getenv("ADMIN_USERS").split(","):
			await interaction.response.send_message("<:pointlaugh:1474657622509486130> You're not allowed to use this command!\n-# Allowed: Admins", ephemeral=True)
			return
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

			await channel.set_permissions(
				interaction.guild.me,
				send_messages=True,
				create_private_threads=True
			)

			webhook: discord.Webhook = await channel.create_webhook(name="AI Plays Mafia", reason="Required for sending AI messages")
			config.setdefault("profiles", {})[str(channel.id)] = {"webhook": webhook.url}

			guild_id_str = str(interaction.guild.id)
			guilds_config = config.setdefault("guilds", {})
			guild_config = guilds_config.get(guild_id_str, {})
			player_role_id = guild_config.get("player_role")
			player = interaction.guild.get_role(player_role_id) if player_role_id else None

			if player is None:
				player = await interaction.guild.create_role(name="Mafia Player")
				guilds_config[guild_id_str] = {"player_role": player.id}

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
			data.update_game_status(self.bot)

			await interaction.response.send_message(f"Mafia game set up in <#{channel.id}>!", ephemeral=True)
		except Exception:
			e = traceback.format_exc()
			await interaction.response.send_message(f"Failed to set up game:\n```python\n{e}\n```")
