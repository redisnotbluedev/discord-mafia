from classes.player import Player, AIAbstraction
from classes.views import VoteView
import discord, random, asyncio, logging, data
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class TurnManager:
	def __init__(self, participants: list[Player], channel: discord.abc.Messageable, bot: discord.Client, client: AsyncOpenAI = None):
		self.participants = participants
		self.channel = channel
		self.client = client or AsyncOpenAI()
		config = data.load()
		self.bot = bot
		webhook_url = None
		try:
			webhook_url = config["profiles"][str(self.channel.id)]["webhook"]
		except Exception:
			webhook_url = None

		self.webhook: discord.Webhook | None = None
		if webhook_url:
			self.webhook = discord.Webhook.from_url(webhook_url, client=bot)

		self.running = False
		self.message_queue = asyncio.Queue()
		self.required_author = -1
		self.context: dict[AIAbstraction, list] = self._initialize_ai_context(participants)

	def _initialize_ai_context(self, participants: list[Player]) -> dict[AIAbstraction, list]:
		"""Initialize AI context with detailed game instructions and rules."""
		context = {}
		for p in participants:
			if isinstance(p.user, AIAbstraction):
				context[p.user] = [
					{
						"role": "system",
						"content": """You are an intelligent AI player in a game of Mafia. Here are the rules:

GAME OVERVIEW:
- The town must identify and eliminate all mafia members during day votes
- The mafia must eliminate town members at night until they equal or outnumber town
- Special roles (Doctor, Sheriff) help the town gather information and protect players

YOUR ROLE AND ABILITIES:
You will be assigned a role at game start. Listen carefully to learn your role details.
- Townsperson: Vote strategically during the day
- Mafia: Vote during the day and discuss targets at night
- Doctor: During night, you can save one player from being killed
- Sheriff: During night, you can investigate one player to learn their alignment (Town/Mafia)

STRATEGY TIPS:
- Pay attention to what other players say - look for suspicious behavior
- If you're special role, keep your identity secret (except Mafia knows each other)
- Use the voting phase to eliminate threats
- Discuss your suspicions and observations with other players
- When making night actions, choose wisely - your decision could save the town or eliminate threats

IMPORTANT: Keep responses concise and natural, as if you're a real player. Don't break character."""
					}
				]
		return context

	def set_channel(self, channel: discord.abc.Messageable):
		self.channel = channel

	def set_participants(self, participants: list[Player]):
		self.participants = participants

	def set_context(self, context: dict[AIAbstraction, list]):
		self.context = context

	def broadcast(self, text, exclude: Player = None):
		"""Broadcast a message to all AI players so they understand game events."""
		for player in self.participants:
			if player != exclude and isinstance(player.user, AIAbstraction):
				self.context.setdefault(player.user, []).append({"role": "user", "content": text})

	def broadcast_to_all_ai(self, text: str):
		"""Broadcast a message to ALL AI players including those not in current round."""
		for player in self.participants:
			if isinstance(player.user, AIAbstraction):
				self.context.setdefault(player.user, []).append({"role": "user", "content": text})

	def get_context(self):
		return self.context

	def _candidate_by_name(self, candidates: list[Player], name: str) -> Player | None:
		name = (name or "").strip()
		for c in candidates:
			if c.name == name:
				return c
		return None

	def _format_vote_tally(self, votes: dict[int, str], candidates: list[Player]) -> str:
		# votes: voter_id -> candidate_name
		counts: dict[str, int] = {c.name: 0 for c in candidates}
		for choice in votes.values():
			if choice in counts:
				counts[choice] += 1

		lines = []
		for c in candidates:
			n = counts.get(c.name, 0)
			lines.append(f"- {c.name}: **{n}**")
		return "\n".join(lines) if lines else "No candidates."

	async def run_round(self):
		self.running = True
		random.shuffle(self.participants)
		for player in self.participants:
			if isinstance(player.user, discord.Member):
				await self.channel.send(f"🎤 {player.user.mention}, it's your turn to speak!")
				if isinstance(self.channel, discord.Thread):
					await self.bot.get_channel(self.channel.parent_id).set_permissions(
						player.user,
						send_messages_in_threads=True
					)
				else:
					await self.channel.set_permissions(
						player.user,
						send_messages=True
					)

				self.required_author = player.user.id
				logger.info("Waiting for message send")
				message = await self.message_queue.get()
				logger.debug(f"Got message: {message.content}")
				self.required_author = -1
				self.broadcast_to_all_ai(f"{player.name} said: {message.content}")
				if isinstance(self.channel, discord.Thread):
					await self.bot.get_channel(self.channel.parent_id).set_permissions(
						player.user,
						send_messages_in_threads=True
					)
				else:
					await self.channel.set_permissions(
						player.user,
						send_messages=True
					)

			elif isinstance(player.user, AIAbstraction):
				await self.channel.send(f"🎤 It's {player.user.name}'s turn to speak!")
				messages = self.context.setdefault(player.user, [])
				response = await self.client.chat.completions.create(
					model=player.user.model,
					messages=messages
				)
				text = response.choices[0].message.content

				if self.webhook:
					await self.webhook.send(
						username=player.name,
						avatar_url=player.user.avatar,
						content=text,
						thread=(self.channel if isinstance(self.channel, discord.Thread) else None)
					)
				else:
					await self.channel.send(f"**{player.name}:** {text}")

				self.broadcast(f"{player.name} said: {text}", player)

	async def run_vote(self, candidates: list[Player], message, placeholder="Vote for a player...", emoji="🗳️", timeout_s=120.0, break_ties_random=False, allow_abstain=False):
		votes: dict[int, str] = {}

		ends_at = int(__import__("time").time() + timeout_s)
		countdown = f"-# Voting ends <t:{ends_at}:R>."
		base_message = message + "\n" + countdown

		view = VoteView(
			players=[p.name for p in candidates],
			placeholder=placeholder,
			emoji=emoji,
			allow_abstain=allow_abstain
		)
		view.votes = votes
		view.allowed_voters = {
			p.user.id for p in self.participants
			if isinstance(p.user, discord.Member)
		}
		view.required_votes = len(view.allowed_voters)
		view.base_message = base_message

		poll = await self.channel.send(
			base_message + "\n\n**Votes:**\nNo votes yet.",
			view=view
		)

		candidate_names = [p.name for p in candidates]
		if allow_abstain:
			candidate_names.append("Abstain")
		options_block = "\n".join(candidate_names)

		# Prepare AI voting tasks to run concurrently
		async def get_ai_vote(ai_player: Player):
			"""Get a single AI player's vote."""
			messages = self.context.setdefault(ai_player.user, [])
			messages.append({
				"role": "user",
				"content": "\n".join([
					message,
					"Vote by replying with EXACTLY ONE line containing EXACTLY ONE of the option names below.",
					"Do not add punctuation, quotes, explanations, or multiple lines.",
					"OPTIONS:",
					options_block
				])
			})

			response = await self.client.chat.completions.create(
				model=ai_player.user.model,
				messages=messages
			)
			choice = (response.choices[0].message.content or "").strip()

			if choice not in candidate_names:
				choice = random.choice(candidate_names)

			return ai_player, choice

		# Gather all AI voting tasks and run concurrently
		ai_players = [p for p in self.participants if isinstance(p.user, AIAbstraction)]
		if ai_players:
			ai_votes = await asyncio.gather(*[get_ai_vote(p) for p in ai_players])
			for ai_player, choice in ai_votes:
				votes[hash(ai_player.name)] = choice
				# Add voting result to context so AIs know what happened
				self.context[ai_player.user].append({"role": "assistant", "content": choice})

		human_voters = [
			p.user for p in self.participants
			if isinstance(p.user, discord.Member)
		]
		expected_human_votes = len(human_voters)

		async def wait_for_human_votes():
			start = asyncio.get_event_loop().time()
			while True:
				got = sum(1 for uid in votes.keys() if uid in view.allowed_voters)
				if got >= expected_human_votes:
					return
				if (asyncio.get_event_loop().time() - start) >= timeout_s:
					return
				await asyncio.sleep(0.5)

		await wait_for_human_votes()

		tally = self._format_vote_tally(votes, candidates)
		if allow_abstain:
			abstain_n = sum(1 for v in votes.values() if v == "Abstain")
			if abstain_n:
				tally = tally + f"\n- Abstain: **{abstain_n}**"
		await poll.edit(content=base_message + "\n\n**Votes:**\n" + tally, view=None)

		counts: dict[str, int] = {name: 0 for name in candidate_names}
		for choice in votes.values():
			if choice in counts:
				counts[choice] += 1

		if allow_abstain and "Abstain" in counts:
			abstain_votes = counts["Abstain"]
			non_abstain_max = max([n for name, n in counts.items() if name != "Abstain"], default=0)
			if abstain_votes >= non_abstain_max:
				return None
			counts.pop("Abstain", None)

		if not any(counts.values()):
			return None

		best = max(counts.values())
		winners = [name for name, n in counts.items() if n == best]
		if len(winners) != 1:
			if break_ties_random and winners:
				picked = random.choice(winners)
				return self._candidate_by_name(candidates, picked)
			return None

		return self._candidate_by_name(candidates, winners[0])

	def on_message(self, message: discord.Message):
		logger.debug(f"Got message '{message.content}' from {message.author.id}, required author is {self.required_author}.")
		if message.author.id == self.required_author and message.content:
			self.message_queue.put_nowait(message)