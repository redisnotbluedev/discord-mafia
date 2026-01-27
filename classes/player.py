import discord
from classes.roles import *

models = [
	{
		"model": "gpt-4o",
		"name": "ChatGPT 4o",
		"avatar_url": "https://media.discordapp.net/attachments/1460808917289533601/1465512821285453964/chatgpt4o.png?ex=697960ac&is=69780f2c&hm=0f8f102918d95575239072772e01b0ee33b5a50cdccf077db0bd1ec45ba5985a&animated=true"
	},
	{
		"model": "deepseek-3.2",
		"name": "DeepSeek 3.2",
		"avatar": "https://media.discordapp.net/attachments/1460808917289533601/1465512822468251729/deepseek.png?ex=697960ac&is=69780f2c&hm=7cfdec6b45dd87eb5ec9e2d63b08f96e72dc9a305a8a6aef9cd9990a36e98b30&animated=true"
	},
	{
		"model": "kimi-k2",
		"name": "Kimi K2",
		"avatar": "https://media.discordapp.net/attachments/1460808917289533601/1465512820811632680/Designer_1.png?ex=697960ac&is=69780f2c&hm=3ce244df7838a40eb92662f1c00944fa1a9914efec7220214608001d68922881&animated=true"
	},
	{
		"model": "llama-4-maverick",
		"name": "Llama 4",
		"avatar": "https://media.discordapp.net/attachments/1460808917289533601/1465512511116939284/llama.png?ex=69796062&is=69780ee2&hm=be5ae39c391c68842ec88312b06bf3ff68a83738172fa0109cc95bd584639731&animated=true"
	},
	{
		"model": "qwen3-next-80b-a3b",
		"name": "Qwen 3",
		"avatar": "https://media.discordapp.net/attachments/1460808917289533601/1465512510785585303/qwen.png?ex=69796062&is=69780ee2&hm=bccbd1ea7ea76bc0b6ff7f7eb7f8a1b81bb510fd67fbf47ff4b2b7cf98fb7a51&animated=true"
	},
	{
		"model": "mistral-large-3",
		"name": "Mistral 3",
		"avatar": "https://media.discordapp.net/attachments/1460808917289533601/1465512511838355656/mistral.png?ex=69796062&is=69780ee2&hm=bc637a4480fd2bc2e3eded35f3133eb840cf19c99dc3a3bc2e8b2d59e2c080aa&animated=true"
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
