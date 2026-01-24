from enum import Enum
import discord

models = {
	"gpt-4o": {
		"name": "4o",
		"avatar": "https://media.discordapp.net/stickers/1457241018561728698.webp?size=160&quality=lossless"
	},
	"qwen-3-next-80b-a3b": {
		"name": "qwen",
		"avatar": "https://upload.wikimedia.org/wikipedia/commons/4/4d/Cheeseburger.jpg"
	},
	"deepseek-3.2": {
		"name": "Winnie the Pooh",
		"avatar": "https://upload.wikimedia.org/wikipedia/en/1/10/Winniethepooh.png"
	},
	"noromaid-7b-v0.2": {
		"name": "noromaid",
		"avatar": "https://static.vecteezy.com/system/resources/previews/025/208/624/non_2x/3d-letter-a-free-png.png"
	},
	"mistral-large-3": {
		"name": "mistral",
		"avatar": "https://i.natgeofe.com/n/548467d8-c5f1-4551-9f58-6817a8d2c45e/NationalGeographic_2572187_16x9.jpg?w=1200"
	},
	"llama-4-maverick": {
		"name": "llama",
		"avatar": "https://nwyarns.com/cdn/shop/articles/Llama_grande.png?v=1512170916"
	},
	"gemini-3-flash": {
		"name": "flash",
		"avatar": "https://i.ytimg.com/vi/KxXp8oiMzSw/hq720.jpg?sqp=-oaymwEhCK4FEIIDSFryq4qpAxMIARUAAAAAGAElAADIQj0AgKJD&rs=AOn4CLAGu-LjIDP_7vcuMCgVar1CYR0QJA"
	}
}

class Role(Enum):
	TOWN = 0
	MAFIA = 1
	DOCTOR = 2
	SHERIFF = 3

	def __str__(self):
		return self.name.title()

	def describe(self):
		match self:
			case Role.TOWN:
				return "a **Townsperson**.\n> You are an ordinary citizen. Your goal is to identify and eliminate the Mafia during day votes. You have no special abilities, but you can use your voice and vote to help the town survive."
			case Role.MAFIA:
				return "part of the **Mafia**.\n> You are part of the Mafia! During the night phase, you and your fellow Mafia members secretly choose one player to eliminate. Your goal is to eliminate all other players without being caught. During the day, blend in and avoid suspicion."
			case Role.DOCTOR:
				return "a **Doctor**.\n> You can save one player from elimination each night. Choose wisely! If you select the same player the Mafia targeted, you'll prevent their death. You **are** allowed to save yourself, and you must help the town identify the Mafia during day votes."
			case Role.SHERIFF:
				return "a **Sheriff**.\n> You can investigate one player each night to determine if they are part of the Mafia. Use this information carefully during day discussions to guide the town's votes, but be cautious - revealing yourself may make you a target!"

	def alignment(self):
		match self:
			case Role.TOWN | Role.DOCTOR | Role.SHERIFF:
				return "Town"
			case Role.MAFIA:
				return "Mafia"

	def is_special(self):
		return self in [Role.DOCTOR, Role.SHERIFF]

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
		self.last_night_acted: int | None = None

def create_ai_players() -> list[Player]:
	players = []

	for id, data in models.items():
		model = AIAbstraction(id, data.get("name", "Unknown AI"), data.get("avatar"))
		players.append(model.player)

	return players
