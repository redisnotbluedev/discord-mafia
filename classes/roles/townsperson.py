from classes.roles import Role, Alignment

class Town(Role):
	def __init__(self):
		super().__init__("Town", Alignment.TOWN, "**Town**.\n> You are an ordinary citizen. Your goal is to identify and eliminate the Mafia during day votes. You have no special abilities, but you can use your voice and vote to help the town survive.", "Ordinary citizen who votes to eliminate Mafia.")

TOWN = Town()
