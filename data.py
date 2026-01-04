import json

def save(data: dict):
	with open("data.json", "w") as f:
		json.dump(f)

def load():
	with open("data.json") as f:
		return json.load(f) or {}