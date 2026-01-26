from classes.roles import SaveRole, Alignment

class Doctor(SaveRole):
	def __init__(self):
		super().__init__("Doctor", Alignment.TOWN, "a **Doctor**.\n> You can save one player from elimination each night. Choose wisely! If you select the same player the Mafia targeted, you'll prevent their death. You **are** allowed to save yourself, and you must help the town identify the Mafia during day votes.")

	async def handle_button_click(self, game, player, interaction):
		import discord
		from classes.views import SelectView
		last_saved = player.role_state.get("last_saved")
		select_view = SelectView([
			discord.SelectOption(label=p.name, value=str(i), emoji="💊", description="Can't save twice in a row" if last_saved and p == last_saved else None)
			for i, p in enumerate(game.get_alive_players()) if p.alive
		], lambda inter: self.on_save_selected(game, player, inter))
		await interaction.response.send_message(self.get_prompt(), view=select_view, ephemeral=True)

	async def on_save_selected(self, game, player, interaction):
		index = int(interaction.values[0])
		user = game.get_alive_players()[index]
		last_saved = player.role_state.get("last_saved")
		if last_saved and user == last_saved:
			await interaction.response.edit_message(content=f"You can't save {user.name} twice in a row!", view=None)
			return
		await self.handle_save_selection(game, player, user)
		await interaction.response.edit_message(content=f"You chose to save {user.name}.", view=None)

	async def night_action_ai(self, game, player):
		last_saved = player.role_state.get("last_saved")
		available = [p for p in game.get_alive_players() if p.alive and (not last_saved or p != last_saved)]
		if not available:
			return
		prompt = f"NIGHT: {self.name.upper()} SAVE\n> Who do you want to save? Reply with EXACTLY ONE player name, nothing else.\nAvailable players to save:\n{"\n".join([f"- {p.name}" for p in available])}"
		choice_text = await game.turns.create_ai_completion(player, prompt)
		chosen = None
		for p in available:
			if p.name.lower() in choice_text.lower():
				chosen = p
				break
		if not chosen:
			chosen = available[0]
		if chosen:
			await self.handle_save_selection(game, player, chosen)

DOCTOR = Doctor()