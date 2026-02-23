from classes.roles import InvestigateRole, Alignment

class Sheriff(InvestigateRole):
	def __init__(self):
		super().__init__("Sheriff", Alignment.TOWN, 'a **Sheriff**.\n> You can investigate one player each night to determine if they are part of the Mafia. Use this information carefully during day discussions to guide the town\'s votes, but be cautious - revealing yourself may make you a target!', 'Can investigate a player\'s alignment each night.')
		self.emoji = "🤠"

SHERIFF = Sheriff()