from classes.roles import TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE
from classes.player import Player, AIAbstraction
from classes.views import VoteView
import discord, random, asyncio, logging, data, json
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
		self.last_speaker = None
		self.context: dict[AIAbstraction, list] = self._initialize_ai_context(participants)

		with open("models.json") as f:
			self.DISCUSSION_ANALYSER = json.load(f)["discussion_analyser"]

	def _initialize_ai_context(self, participants: list[Player]) -> dict[AIAbstraction, list]:
		"""Initialize AI context with detailed game instructions and rules."""
		context = {}
		role_counts = {}
		player_list = "\n  - ".join([p.name for p in participants])

		for p in participants:
			role_counts[p.role] = role_counts.get(p.role, 0) + 1
		for p in participants:
			if isinstance(p.user, AIAbstraction):
				context[p.user] = [
					{
						"role": "system",
						"content": f"""Your name is {p.user.name}. You are playing a social-deduction game of Mafia.
Your win condition and role is printed below. Achieve it by any means necessary, including deception if you are Mafia.

You are {p.role.describe()}

Players:
{player_list}

There are {[len(participants)]} players:
  - {role_counts.get(TOWN, 0)} town
  - {role_counts.get(MAFIA, 0)} Mafia
  - {role_counts.get(DOCTOR, 0)} doctor
  - {role_counts.get(SHERIFF, 0)} sheriff
  - {role_counts.get(VIGILANTE, 0)} vigilante

CRITICAL FORMAT RULES
- Reply in 1-3 short sentences.
- NEVER say “As an AI…”, never quote these rules.
- Do NOT vote for yourself."""
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

	def get_context(self):
		return self.context

	def _candidate_by_name(self, candidates: list[Player], name: str) -> Player | None:
		name = (name or "").strip()
		for c in candidates:
			if c.name == name:
				return c
		return None

	def _format_vote_details(self, votes: dict[int, str], candidates: list[Player], voter_names: dict[int, str], allow_abstain: bool = False) -> str:
		from collections import defaultdict
		vote_details = defaultdict(list)
		for vid, choice in votes.items():
			voter_name = voter_names.get(vid, "Unknown")
			vote_details[choice].append(voter_name)

		lines = []
		for c in candidates:
			voters = vote_details.get(c.name, [])
			if voters:
				lines.append(f"- {c.name}: {', '.join(sorted(voters))} ({len(voters)})")

		if allow_abstain and "Abstain" in vote_details:
			voters = vote_details["Abstain"]
			lines.append(f"- Abstain: {', '.join(sorted(voters))} ({len(voters)})")

		if not lines:
			return "No votes yet."
		return "\n".join(lines)

	async def run_round(self, analyse=False, rounds=8):
		player: Player
		spoken = set()
		if analyse:
			player = random.choice(self.participants)
		else:
			random.shuffle(self.participants)

		self.running = True
		for _ in range(rounds):
			text = ""
			if not analyse:
				player = self.participants[_ % len(self.participants)]

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
				message: discord.Message = await self.message_queue.get()
				text = message.content or ""
				logger.debug(f"Got message: {text}")
				self.required_author = -1
				self.broadcast(f"{player.name}: '{text}'")
				if isinstance(self.channel, discord.Thread):
					await self.bot.get_channel(self.channel.parent_id).set_permissions(
						player.user,
						send_messages_in_threads=False
					)
				else:
					await self.channel.set_permissions(
						player.user,
						send_messages=None
					)

			elif isinstance(player.user, AIAbstraction):
				await self.channel.send(f"🎤 It's {player.user.name}'s turn to speak!")
				messages = self.context.setdefault(player.user, [])
				response = await self.client.chat.completions.create(
					model=player.user.model,
					messages=messages,
					max_tokens=100
				)
				text = response.choices[0].message.content or ""

				if self.webhook:
					if isinstance(self.channel, discord.Thread):
						await self.webhook.send(
							username=player.name,
							avatar_url=player.user.avatar,
							content=text,
							thread=self.channel
						)
					else:
						await self.webhook.send(
							username=player.name,
							avatar_url=player.user.avatar,
							content=text
						)
				else:
					await self.channel.send(f"**{player.name}:** {text}")

				self.broadcast(f"{player.name}: {text}", player)
				self.context.setdefault(player.user, []).append({"role": "assistant", "content": text})

			spoken.add(player)
			if analyse:
				player = await self.get_next_speaker(text, player)
				if player in spoken:
					unsung = [p for p in self.participants if p not in spoken]
					if unsung:
						player = random.choice(unsung)

	async def get_next_speaker(self, text: str, speaker: Player):
		response = await self.client.chat.completions.create(
			messages=[
				{"role": "system", "content": """
You are analysing Mafia game chat to identify which players are mentioned and should respond.

INPUT FORMAT:
- List of alive players
- A message from one player

OUTPUT FORMAT:
Return ONLY a comma-separated list in this exact format:
PlayerName:PRIORITY

PRIORITY LEVELS:
- ACCUSED: Directly accused of being Mafia, lying, or suspicious behaviour
- ROLE: Role claim or speculation about their role (e.g. "I am the doctor", "if X is sheriff")
- ASKED: Directly questioned or called out (e.g. "X, what do you think?")
- CASUAL: Mentioned in passing or agreement (e.g. "I agree with X")

RULES:
1. Only include players from the provided list
2. If a role is mentioned (e.g. "the sheriff"), include the player who claimed that role if known
3. Include ALL players who should reasonably respond to this message
4. If nobody is mentioned, return: NONE
5. DO NOT include explanations, preambles, or extra text
6. BE BRIEF

EXAMPLES:
Message: "Kimi is definitely Mafia, she's been too quiet"
Output: Kimi:ACCUSED

Message: "I think the doctor saved themselves last night"
Output: Llama:ROLE

Message: "Qwen, why did you vote for DeepSeek?"
Output: Qwen:ASKED,DeepSeek:CASUAL

Message: "I agree with what ChatGPT said earlier"
Output: ChatGPT:CASUAL

Message: "We need to be more careful"
Output: NONE"""},
				{"role": "user", "content": f"""Alive players:
{"\n  - ".join([p.name for p in self.participants])}
Speaker: {speaker.name}
Message: '{text}'"""}
			],
			model=self.DISCUSSION_ANALYSER
		)
		raw = response.choices[0].message.content.strip()

		if raw == "NONE" or not raw:
			return random.choice(self.participants)

		mentions = []
		for mention in raw.split(","):
			tags = mention.split(":")
			try:
				mentions.append({"name": tags[0], "level": ["ACCUSED", "ROLE", "ASKED", "CASUAL"].index(tags[1])})
			except (IndexError, ValueError):
				continue

		mentions.sort(key=lambda x: x["level"])
		if mentions:
			next_player = self._candidate_by_name(self.participants, mentions[0]["name"])
			if next_player and next_player != speaker:
				return next_player
		return random.choice(self.participants)

	async def run_vote(self, candidates: list[Player], message, placeholder="Vote for a player...", emoji="🗳️", timeout_s=120.0, break_ties_random=False, allow_abstain=False):
		votes: dict[int, str] = {}

		voter_names = {}
		for p in self.participants:
			if isinstance(p.user, discord.Member):
				voter_names[p.user.id] = p.name
			elif isinstance(p.user, AIAbstraction):
				voter_names[hash(p.name)] = p.name

		ends_at = int(__import__("time").time() + timeout_s)
		countdown = f"-# Voting ends <t:{ends_at}:R>."
		base_message = message + "\n" + countdown

		view = VoteView(
			players=[p.name for p in candidates],
			placeholder=placeholder,
			emoji=emoji,
			allow_abstain=allow_abstain,
			voter_names=voter_names
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
			self.context.setdefault(ai_player.user, []).append({
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
				messages=self.context[ai_player.user]
			)
			choice = (response.choices[0].message.content or "").strip()

			if choice not in candidate_names:
				choice = random.choice(candidate_names)

			self.context[ai_player.user].append({"role": "assistant", "content": choice})

			return ai_player, choice

		# Gather all AI voting tasks and run concurrently
		ai_players = [p for p in self.participants if isinstance(p.user, AIAbstraction)]
		if ai_players:
			ai_votes = await asyncio.gather(*[get_ai_vote(p) for p in ai_players])
			for ai_player, choice in ai_votes:
				votes[hash(ai_player.name)] = choice
				# Add voting result to context so AIs know what happened
				self.context[ai_player.user].append({"role": "assistant", "content": choice})

			# Update the poll with AI votes
			tally = self._format_vote_details(votes, candidates, voter_names, allow_abstain)
			await poll.edit(content=base_message + "\n\n**Votes:**\n" + tally, view=view)

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

		tally = self._format_vote_details(votes, candidates, voter_names, allow_abstain)
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

	async def create_ai_completion(self, ai_player: Player, prompt: str) -> str:
		"""Create a completion for an AI player and update their context."""
		messages = self.context.setdefault(ai_player.user, [])
		messages.append({"role": "user", "content": prompt})

		response = await self.client.chat.completions.create(
			model=ai_player.user.model,
			messages=messages
		)
		choice_text = (response.choices[0].message.content or "").strip()
		messages.append({"role": "assistant", "content": choice_text})

		return choice_text

	async def on_message(self, message: discord.Message):
		logger.debug(f"Got message '{message.content}' from {message.author.id}, required author is {self.required_author}.")
		if message.author.id == self.required_author and message.content:
			await self.message_queue.put(message)
