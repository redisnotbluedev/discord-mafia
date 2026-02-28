from discord.ext import commands
from discord import app_commands
import discord, json
from classes.player import AIAbstraction

class GamesCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot: commands.Bot = bot

	@app_commands.command(name="kick", description="Kick a player from this game.")
	async def kick(self, interaction: discord.Interaction, player: discord.User):
		if interaction.user == player:
			await interaction.response.send_message("You can't kick yourself.", ephemeral=True)
			return

		abstractor = next((a for a in self.bot.abstractors if a.channel == interaction.channel.id), None)
		if abstractor:
			if abstractor.owner == interaction.user:
				if player.id in abstractor.players:
					del abstractor.players[player.id]

				scheduler = getattr(abstractor.game, "scheduler", None)
				if scheduler and scheduler.lobby:
					await scheduler.message.edit(embed=scheduler.lobby.generate_embed(), view=scheduler.lobby)
				await interaction.response.send_message(f"Kicked {player.mention} from the game.")
			else:
				await interaction.response.send_message("You need to be the owner of this game to kick players.", ephemeral=True)
		else:
			await interaction.response.send_message("There's no ongoing game in this channel.", ephemeral=True)

	@app_commands.command(name="llama10", description="Removes all AIs and creates a game with 10 Llama 4 players.")
	async def llama10(self, interaction: discord.Interaction):
		abstractor = next((a for a in self.bot.abstractors if a.channel == interaction.channel.id), None)
		if not abstractor or not abstractor.running:
			await interaction.response.send_message("There's no lobby active in this channel. Send a message to create one.", ephemeral=True)
			return

		if abstractor.owner != interaction.user:
			await interaction.response.send_message("You need to be the owner of this game to do this.", ephemeral=True)
			return

		humans = {k: v for k, v in abstractor.players.items() if isinstance(v.user, discord.Member)}
		abstractor.players.clear()
		abstractor.players.update(humans)

		try:
			with open("models.json") as f:
				m_data = json.load(f)
				llama_meta = next((m for m in m_data["models"] if m["model"] == "llama-4-maverick"), None)
				avatar_format = m_data["avatar_template"]
		except Exception:
			await interaction.response.send_message("Failed to load models.json", ephemeral=True)
			return

		if not llama_meta:
			await interaction.response.send_message("Llama 4 model not found in models.json", ephemeral=True)
			return

		for i in range(10):
			avatar = llama_meta.get("avatar") or llama_meta.get("avatar_url")
			ai_user = AIAbstraction(llama_meta["model"], llama_meta["name"], avatar_format.format(avatar))
			abstractor.players[hash(f"{ai_user.name}_{i}")] = ai_user.player

		scheduler = getattr(abstractor.game, "scheduler", None)
		if scheduler and scheduler.lobby:
			new_embed = scheduler.lobby.generate_embed()

			total_players = len(abstractor.players)
			current_mafia = scheduler.config.get("mafia", 0)
			current_town = scheduler.config.get("town", 0)

			if current_mafia + current_town > total_players:
				scheduler.config["town"] = max(1, total_players - current_mafia)
			elif current_mafia + current_town < total_players:
				scheduler.config["town"] = current_town + (total_players - (current_mafia + current_town))

			if scheduler.config["mafia"] > scheduler.config["town"]:
				scheduler.config["mafia"] = scheduler.config["town"]

			# Also update the config models to Llama 4 so SettingsView syncs correctly
			scheduler.config["models"] = ["llama-4-maverick"]

			# Re-generate embed after config changes to ensure counts are right
			await scheduler.message.edit(embed=scheduler.lobby.generate_embed(), view=scheduler.lobby)
			await interaction.response.send_message("Replaced AIs with 10 Llama 4 players.")
		else:
			await interaction.response.send_message("Lobby initialized with 10 Llama 4 players (Note: embed update failed).")
