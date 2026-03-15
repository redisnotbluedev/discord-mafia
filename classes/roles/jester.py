from classes.player import Player
from classes.roles import Role, Alignment

class Jester(Role):
	"""Neutral role that wins by getting lynched during a day vote."""

	def __init__(self):
		super().__init__("Jester", Alignment.NEUTRAL, "a **Jester**.\n> You win if you get lynched by the town. Trick them into voting for you!", "Wins if lynched by the town.", "🤡")

	def win_condition(self, player: Player, players: list[Player]) -> bool:
		return player.death_reason == "lynch"

JESTER = Jester()
