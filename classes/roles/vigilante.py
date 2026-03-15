from classes.roles import KillRole, Alignment

class Vigilante(KillRole):
	def __init__(self):
		super().__init__("Vigilante", Alignment.TOWN, 'a **Vigilante**.\n> You have one bullet and can shoot any player during the night. Pick your shot carefully, since you only have one! Help the town identify Mafia, and shoot anyone if the need arises.', 'Has one shot to kill a player at night.', skippable=True)

	def can_act(self, player):
		return not player.role_state.get("has_shot", False)

	async def handle_button_click(self, game, player, interaction, action_view=None):
		if not self.can_act(player):
			await interaction.response.send_message("You have already used your shot!", ephemeral=True)
			if action_view:
				action_view.pending_humans.discard(interaction.user.id)
			return
		await super().handle_button_click(game, player, interaction, action_view)

	async def handle_selection(self, game, player, user):
		await super().handle_selection(game, player, user)
		player.role_state["has_shot"] = True

VIGILANTE = Vigilante()
