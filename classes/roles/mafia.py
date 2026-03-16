from classes.roles import KillRole, Alignment

class Mafia(KillRole):
	"""Mafia team member who votes on a kill target each night.

	Overrides is_special() to return False because the mafia kill is
	handled collectively via mafia_choose_target(), not as an
	individual night action button.
	"""

	def __init__(self, skippable: bool = False):
		super().__init__("Mafia", Alignment.MAFIA, 'a **Mafia**.\n> Your goal is to eliminate all members of the Town. Work with your fellow Mafia members to choose a target each night and avoid suspicion during the day.', 'Can kill one player each night with their team.', skippable=skippable)
		self.emoji = "🔪"

	def is_special(self) -> bool:
		return False

MAFIA = Mafia()