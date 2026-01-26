from classes.roles import InvestigateRole, Alignment

class Sheriff(InvestigateRole):
	def __init__(self):
		super().__init__("Sheriff", Alignment.TOWN, "a **Sheriff**.\n> You can investigate one player each night to determine if they are part of the Mafia. Use this information carefully during day discussions to guide the town's votes, but be cautious - revealing yourself may make you a target!")

	def get_button_info(self):
		return {"label": "Sheriff", "emoji": "🤠"}

	async def night_action_ai(self, game, player):
		prompt = f"NIGHT: {self.name.upper()} INVESTIGATION\n> Pick ONE living player to check (you can't inspect yourself). Available players: {"\n".join([f"- {p.name}" for p in game.get_alive_players() if p.alive and p != player])}"
		choice_text = await game.turns.create_ai_completion(player, prompt)
		chosen = None
		for p in game.get_alive_players():
			if p.alive and p != player and p.name.lower() in choice_text.lower():
				chosen = p
				break
		if not chosen:
			chosen = next((p for p in game.get_alive_players() if p.alive and p != player), None)
		if chosen:
			await self.handle_investigate_selection(game, player, chosen)

SHERIFF = Sheriff()