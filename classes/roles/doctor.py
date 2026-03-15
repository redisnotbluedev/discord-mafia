from typing import TYPE_CHECKING

from classes.roles import SaveRole, Alignment
if TYPE_CHECKING:
	from classes.game import MafiaGame
	from classes.player import Player

class Doctor(SaveRole):
	"""Town healer who can protect one player per night.

	Cannot save the same person on consecutive nights (tracked via
	player.role_state['last_saved']).  Can save self.
	"""

	def __init__(self):
		super().__init__("Doctor", Alignment.TOWN, 'a **Doctor**.\n> You can save one player from elimination each night. Choose wisely! If you select the same player the Mafia targeted, you\'ll prevent their death. You **are** allowed to save yourself, but you cannot protect the same person twice in a row. You must help the town identify the Mafia during day votes.', 'Can save a player from dying each night, but not the same person twice in a row.')

	def get_options(self, game: "MafiaGame", player: "Player") -> "list[Player]":
		"""Get the list of players the doctor can save.

		Args:
			game: The game instance.
			player: The doctor player.

		Returns:
			A list of players the doctor can save.
		"""
		last_saved = player.role_state.get("last_saved")
		return [p for p in game.get_alive_players() if p.alive and (not last_saved or p != last_saved)]

DOCTOR = Doctor()