from classes.roles import Role, Alignment

class Mafia(Role):
	def __init__(self):
		super().__init__("Mafia", Alignment.MAFIA, "part of the **Mafia**.\n> You are part of the Mafia! During the night phase, you and your fellow Mafia members secretly choose one player to eliminate. Your goal is to eliminate all other players without being caught. During the day, blend in and avoid suspicion.")

MAFIA = Mafia()