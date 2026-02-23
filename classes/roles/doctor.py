from classes.roles import SaveRole, Alignment

class Doctor(SaveRole):
	def __init__(self):
		super().__init__("Doctor", Alignment.TOWN, 'a **Doctor**.\n> You can save one player from elimination each night. Choose wisely! If you select the same player the Mafia targeted, you\'ll prevent their death. You **are** allowed to save yourself, and you must help the town identify the Mafia during day votes.', 'Can save a player from dying each night.')

	def get_options(self, game, player):
		last_saved = player.role_state.get("last_saved")
		return [p for p in game.get_alive_players() if p.alive and (not last_saved or p != last_saved)]

DOCTOR = Doctor()