"""Simple JSON file persistence for bot configuration.

Stores channel profiles, webhook URLs, guild configs, and lobby state
in data.json.  Uses a read-modify-write pattern.
"""

import json, logging, os

logger = logging.getLogger(__name__)

def save(data: dict):
	"""Write the entire config dict to data.json, overwriting previous contents."""
	logger.info("Saving data to disk...")
	with open("data.json", "w") as f:
		json.dump(data, f)

def load():
	"""Load config from data.json, creating an empty file if it doesn't exist."""
	try:
		with open("data.json", "r") as f:
			return json.load(f) or {}
	except (FileNotFoundError, json.JSONDecodeError):
		with open("data.json", "w") as f:
			f.write("{}")
		return {}

def update_game_status(bot):
	"""Updates the games_ongoing.txt file based on whether any games are currently running."""
	running = any(abstractor.running for abstractor in getattr(bot, "abstractors", []))
	status = "1" if running else "0"
	
	try:
		if os.path.exists("games_ongoing.txt"):
			with open("games_ongoing.txt", "r") as f:
				if f.read().strip() == status:
					return

		with open("games_ongoing.txt", "w") as f:
			f.write(status)
	except Exception as e:
		logger.error(f"Failed to update game status file: {e}")
