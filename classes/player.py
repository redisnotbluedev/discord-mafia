"""Player representations for Discord users and AI models.

Provides Player (the in-game wrapper) and AIAbstraction (a duck-typed
stand-in for discord.Member used by AI players).  Also provides
create_ai_players() to build the AI player list from models.json.
"""

from typing import Any, Literal

import discord, json
from classes.roles import *

class AIAbstraction:
	"""Representation of an AI player. Partially compatible with Player.

	Provides .id, .name, and .avatar so code that operates on players
	can use isinstance() checks rather than separate code paths.
	The .id is always -1.

	Attributes:
		model: The OpenAI model identifier (e.g. 'gpt-4o').
		name: Display name shown in Discord.
		avatar: URL for the player's webhook avatar image.
		player: Back-reference to the Player wrapper.
	"""

	def __init__(self, model, name, avatar_url=None):
		self.model = model
		self.id = -1 # compat with discord.User
		self.name = name
		self.avatar = avatar_url
		self.player = Player(self)

class Player:
	"""In-game wrapper for a human or AI participant.

	Attributes:
		user: The underlying discord.Member or AIAbstraction.
		role: The assigned Role instance (set during setup_roles).
		name: Display name (may be deduplicated in the lobby).
		alive: Whether this player is still in the game.
		role_state: Dict for per-player role state (e.g. vigilante shot
			count, doctor protection target).
		death_reason: How this player died ('lynch', 'mafia', 'vigilante',
			'modkill'), or None if still alive.
	"""

	def __init__(self, user: discord.Member | AIAbstraction):
		self.user: discord.Member | AIAbstraction = user
		self.role: Role | None = None
		self.name: str = user.name
		self.alive: bool = True
		self.role_state: dict[str, Any] = {}
		self.death_reason: Literal["lynch", "mafia", "vigilante", "modkill", None] = None

	@property
	def role_or_die(self):
		if self.role is None:
			raise TypeError("role unexpectedly none")
		return self.role

def create_ai_players(selected_models: list[str] | None = None) -> list[Player]:
	"""Create AI Player instances from models.json.

	Reads the models list and avatar template from models.json.  If
	selected_models is provided, only creates players for models in
	that list; otherwise creates players for all models.

	Args:
		selected_models: Optional whitelist of model identifiers.
			If None, all models from models.json are included.

	Returns:
		List of Player instances (accessible via ai_abstraction.player).
	"""
	players = []
	with open("models.json") as f:
		data = json.load(f)
		models = data["models"]
		avatar_format = data["avatar_template"]

	for m in models:
		if selected_models is not None and m["model"] not in selected_models:
			continue
		avatar = m.get("avatar") or m.get("avatar_url")
		model = AIAbstraction(m["model"], m.get("name", "Unknown"), avatar_format.format(avatar))
		players.append(model.player)

	return players
