import discord

from classes.game import MafiaGame
from classes.player import Player
from classes.roles import KillRole, Alignment
from classes.views import SpecialActionsView

class Vigilante(KillRole):
	"""Town role with a single-use kill shot.

	Can opt to skip ('abstain') each night.  Once the shot is fired,
	player.role_state['has_shot'] is set True and the action becomes
	unavailable.
	"""

	def __init__(self):
		super().__init__("Vigilante", Alignment.TOWN, 'a **Vigilante**.\n> You have one bullet and can shoot any player during the night. Pick your shot carefully, since you only have one! Help the town identify Mafia, and shoot anyone if the need arises.', 'Has one shot to kill a player at night.', skippable=True)

	def can_act(self, player: Player):
		"""Return whether the vigilante can act (has not already shot).

		Args:
			player: The vigilante player.

		Returns:
			True if the vigilante can act, False otherwise.
		"""
		# "Has" refers to "has already shot", not "has a bullet available".
		return not player.role_state.get("has_shot", False)

	async def handle_button_click(self, game: MafiaGame, player: Player, interaction: discord.Interaction, action_view: SpecialActionsView | None=None):
		if not self.can_act(player):
			await interaction.response.send_message("You have already used your shot!", ephemeral=True)
			if action_view:
				action_view.pending_humans.discard(interaction.user.id)
			return
		await super().handle_button_click(game, player, interaction, action_view)

	async def handle_selection(self, game: MafiaGame, player: Player, user: Player):
		await super().handle_selection(game, player, user)
		player.role_state["has_shot"] = True

VIGILANTE = Vigilante()
