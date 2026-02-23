from classes.roles import KillRole, Alignment

class Mafia(KillRole):
	def __init__(self, skippable: bool = False):
		super().__init__("Mafia", Alignment.MAFIA, 'a **Mafia**.\n> Your goal is to eliminate all members of the Town. Work with your fellow Mafia members to choose a target each night and avoid suspicion during the day.', 'Can kill one player each night with their team.', skippable=skippable)

	def is_special(self):
		return False

MAFIA = Mafia()