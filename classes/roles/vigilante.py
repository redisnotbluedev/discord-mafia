from classes.roles import KillRole, Alignment

class Vigilante(KillRole):
	def __init__(self):
		super().__init__("Vigilante", Alignment.TOWN, "a **Vigilante**.\n> You have one bullet and can shoot any player during the night. Pick your shot carefully, since you only have one! Help the town identify Mafia, and shoot anyone if the need arises.")

	async def handle_button_click(self, game, player, interaction):
		if player.role_state.get("has_shot", False):
			await interaction.response.send_message("You have already used your shot!", ephemeral=True)
			return
		await super().handle_button_click(game, player, interaction)

	async def on_kill_selected(self, game, player, interaction):
		index = int(interaction.values[0])
		user = game.get_alive_players()[index]
		await self.handle_kill_selection(game, player, user)
		player.role_state["has_shot"] = True
		await interaction.response.edit_message(content=f"You chose to kill {user.name}.", view=None)

	async def night_action_ai(self, game, player):
		if player.role_state.get("has_shot", False):
			return
		prompt = f"NIGHT: {self.name.upper()} KILL\n> Who do you want to kill? Reply with EXACTLY ONE player name, nothing else.\nAvailable players to kill:\n{"\n".join([f"- {p.name}" for p in game.get_alive_players() if p.alive])}"
		choice_text = await game.turns.create_ai_completion(player, prompt)
		chosen = None
		for p in game.get_alive_players():
			if p.alive and p.name.lower() in choice_text.lower():
				chosen = p
				break
		if not chosen:
			chosen = next((p for p in game.get_alive_players() if p.alive), None)
		if chosen:
			await self.handle_kill_selection(game, player, chosen)
			player.role_state["has_shot"] = True

VIGILANTE = Vigilante()
