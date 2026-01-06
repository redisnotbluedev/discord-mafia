import discord

models = {
	"mapleai~gpt-5.2": {
		"name": "ChatGPT 5.2",
		"avatar": None
	},
	"mapleai~gpt-4o": {
		"name": "ChatGPT 4o",
		"avatar": None
	},
	"mapleai~kimi-k2-0905": {
		"name": "Kimi K2",
		"avatar": None
	},
	"mapleai~deepseek-r1-0528": {
		"name": "DeepSeek R1",
		"avatar": None
	},
	"mapleai~gemini-3-flash-preview": {
		"name": "Gemini 3 Flash",
		"avatar": None
	},
	"mapleai~gemini-3-pro-preview": {
		"name": "Gemini 3 Pro",
		"avatar": None
	},
	"mapleai~claude-opus-4.5": {
		"name": "Claude Opus 4.5",
		"avatar": None
	},
	"mapleai~claude-sonnet-4.5": {
		"name": "Claude Sonnet 4.5",
		"avatar": None
	},
	"mapleai~grok-4": {
		"name": "Grok 4",
		"avatar": None
	}
}

class AIAbstraction:
	def __init__(self, model, name, avatar_url=None):
		self.model = model
		self.name = name
		self.avatar = avatar_url
		self.player = Player(self)

class Player:
	def __init__(self, user: discord.User | AIAbstraction):
		self.user = user

def create_ai_players() -> list[Player]:
	players = []

	for id, data in models.items():
		model = AIAbstraction(id, data.get("name", "Unknown AI"), data.get("avatar"))
		players.append(model.player)
	
	return players