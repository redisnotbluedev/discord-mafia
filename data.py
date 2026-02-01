import json, logging

logger = logging.getLogger(__name__)

def save(data: dict):
	logger.info("Saving data to disk...")
	with open("data.json", "w") as f:
		json.dump(data, f)

def load():
	try:
		with open("data.json", "r") as f:
			return json.load(f) or {}
	except (FileNotFoundError, json.JSONDecodeError):
		with open("data.json", "w") as f:
			f.write("{}")
		return {}
