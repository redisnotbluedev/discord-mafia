import discord

class Player:
	def __init__(self, user: discord.User | str):
		self.user = user

def create_ai_players() -> list[Player]:
	return [
		Player("mapleai~gpt-5.2"),
		Player("mapleai~gpt-4o"),
		Player("mapleai~kimi-k2-0905"),
		Player("mapleai~deepseek-r1-0528"),
		Player("mapleai~gemini-3-flash-preview"),
		Player("mapleai~gemini-3-pro-preview"),
		Player("mapleai~claude-opus-4.5"),
		Player("mapleai~claude-sonnet-4.5"),
		Player("mapleai~grok-4"),
		# no llama 4
	]