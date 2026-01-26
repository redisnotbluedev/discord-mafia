from classes.roles import Role, Alignment

class Jester(Role):
	def __init__(self):
		super().__init__("Jester", Alignment.NEUTRAL, "a **Jester**.\n> You win if you get lynched by the town. Trick them into voting for you!")

	def win_condition(self, player, players):
		return player.death_reason == "lynch"

JESTER = Jester()
