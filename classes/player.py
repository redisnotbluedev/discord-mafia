import discord
from classes.roles import *

models = [
	{
		"model": "gpt-4o",
		"name": "Gemini",
		"avatar": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Google_Gemini_icon_2025.svg/960px/Google_Gemini_icon_2025.svg.png"
	},
	{
		"model": "gpt-4o",
		"name": "ChatGPT",
		"avatar_url": "https://cdn.discordapp.com/guilds/1449548216931586260/users/561150467552444436/avatars/175173b9270c081cc1e04fad961231a8.webp?size=128"
	},
	{
		"model": "gpt-4o",
		"name": "DeepSeek",
		"avatar": "https://cdn.discordapp.com/avatars/1292256566518747219/2081952934f3212a5086fb38fa1f91d7.webp?size=128"
	},
	{
		"model": "mistral-large-3",
		"name": "Claude",
		"avatar": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b0/Claude_AI_symbol.svg/960px-Claude_AI_symbol.svg.png"
	},
	{
		"model": "mistral-large-3",
		"name": "Grok",
		"avatar": "https://cdn.discordapp.com/avatars/1457791629120372747/f4839d9d3feb47c0ca071254f3a9c88b.webp?size=128"
	},
	{
		"model": "mistral-large-3",
		"name": "Kimi",
		"avatar": "https://cdn.discordapp.com/avatars/1394070345308311662/4fa6961ff5e7aa15c662675da2e4b1e9.webp?size=128"
	}
]

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

	for m in models:
		model = AIAbstraction(m["model"], m.get("name", "Unknown"), m.get("avatar"))
		players.append(model.player)

	return players
