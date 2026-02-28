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
				
				from classes.scheduler import MafiaSheduler
				scheduler = abstractor.game
				if isinstance(scheduler, MafiaSheduler) and scheduler.lobby:
					await scheduler.message.edit(embed=scheduler.lobby.generate_embed())
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

		abstractor.players = {k: v for k, v in abstractor.players.items() if isinstance(v.user, discord.Member)}

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
			# Use a unique name during creation; generate_embed will handle the clean (n) suffixing
			name = f"{llama_meta['name']} #{i+1}"
			ai_user = AIAbstraction(llama_meta["model"], name, avatar_format.format(avatar))
			abstractor.players[hash(f"{ai_user.name}_{i}")] = ai_user.player

		from classes.scheduler import MafiaSheduler
		scheduler = abstractor.game
		if isinstance(scheduler, MafiaSheduler) and scheduler.lobby:
			# Force the suffixing logic by calling generate_embed
			# This updates Player.name for everyone in abstractor.players
			new_embed = scheduler.lobby.generate_embed()
			# Use the same auto-adjustment logic as SettingsView.render
			total_players = len(abstractor.players)
			current_mafia = scheduler.config.get("mafia", 0)
			current_town = scheduler.config.get("town", 0)

			if current_mafia + current_town > total_players:
				scheduler.config["town"] = max(1, total_players - current_mafia)
			elif current_mafia + current_town < total_players:
				scheduler.config["town"] = current_town + (total_players - (current_mafia + current_town))

			if scheduler.config["mafia"] > scheduler.config["town"]:
				scheduler.config["mafia"] = scheduler.config["town"]

			# Re-generate embed after config changes to ensure counts are right
			await scheduler.message.edit(embed=scheduler.lobby.generate_embed())
			await interaction.response.send_message("Replaced AIs with 10 Llama 4 players.")
		else:
			await interaction.response.send_message("Lobby initialized with 10 Llama 4 players.")
