import discord, json
from classes.roles import *

class AIAbstraction:
	def __init__(self, model, name, avatar_url=None):
		self.model = model
		self.display_name = None # compat with discord.User
		self.id = -1 # compat with discord.User
		self.name = name
		self.avatar = avatar_url
		self.player = Player(self)

class Player:
	def __init__(self, user: discord.Member | AIAbstraction):
		self.user = user
		self.role: Role = None
		self.name = user.display_name or user.name
		self.alive = True
		self.role_state = {}  # For role-specific state like vigilante shots, doctor protections
		self.death_reason = None  # "lynch", "mafia", "vigilante", etc.

def create_ai_players() -> list[Player]:
	players = []
	with open("models.json") as f:
		models = json.load(f)["models"]

	for m in models:
		model = AIAbstraction(m["model"], m.get("name", "Unknown"), m.get("avatar"))
		players.append(model.player)

	return players
