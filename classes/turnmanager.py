from classes.roles import TOWN, MAFIA, DOCTOR, SHERIFF, VIGILANTE
from classes.player import Player, AIAbstraction
from classes.views import VoteView
import discord, random, asyncio, logging, data, json, re
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class TurnManager:
	def _clean_ai_content(self, content: str) -> str:
		if not content:
			return ""
		content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL | re.IGNORECASE)
		return content.strip()

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
		self.player_failures: dict[discord.Member | AIAbstraction, int] = {}

		with open("models.json") as f:
			self.DISCUSSION_ANALYSER = json.load(f)["discussion_analyser"]

	async def handle_player_failure(self, player: Player):
		user = player.user
		self.player_failures[user] = self.player_failures.get(user, 0) + 1
		
		if self.player_failures[user] >= 2:
			msg = f"**{player.name}** has been removed from the game for failing to respond twice in a row."
			player.alive = False
			player.death_reason = "modkill"
			await self.channel.send(msg)
			self.broadcast(msg)
		else:
			msg = f"**{player.name}** failed to respond. If this happens again, they will be removed from the game."
			await self.channel.send(msg)
			self.broadcast(msg)

	def extract_choice(self, content: str, options: list[str]) -> str | None:
		if not content:
			return None
		for opt in options:
			if opt.lower() in content.lower():
				return opt
		return None

	def _initialize_ai_context(self, participants: list[Player]) -> dict[AIAbstraction, list]:
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
- NEVER say "As an AI…", never quote these rules.
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

	async def run_round(self, analyse=False, rounds=None):
		player: Player
		spoken = set()
		speaker_queue = []
		alive_participants = [p for p in self.participants if p.alive]
		
		if rounds is None:
			rounds = int(len(alive_participants) * 1.5)

		if analyse:
			if alive_participants:
				player = random.choice(alive_participants)
			else:
				return
		else:
			random.shuffle(self.participants)

		self.running = True
		for _ in range(rounds):
			text = ""
			if not analyse:
				alive_participants = [p for p in self.participants if p.alive]
				if not alive_participants:
					break
				player = alive_participants[_ % len(alive_participants)]
			elif _ > 0:
				while speaker_queue and not speaker_queue[0].alive:
					speaker_queue.pop(0)
				
				if speaker_queue:
					player = speaker_queue.pop(0)
				else:
					unsung = [p for p in self.participants if p not in spoken and p.alive]
					if unsung:
						player = random.choice(unsung)
					else:
						alive_participants = [p for p in self.participants if p.alive]
						if alive_participants:
							player = random.choice(alive_participants)
						else:
							break

			if not player or not player.alive:
				continue

			if isinstance(player.user, discord.Member):
				timeout_at = int(__import__("time").time() + 180)
				await self.channel.send(f"> {player.user.mention}, it's your turn to speak! Ends <t:{timeout_at}:R>.")
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
				try:
					msg = await asyncio.wait_for(self.message_queue.get(), timeout=180.0)
					text = msg.content or ""
					self.player_failures[player.user] = 0
				except asyncio.TimeoutError:
					await self.handle_player_failure(player)
					if isinstance(self.channel, discord.Thread):
						await self.bot.get_channel(self.channel.parent_id).set_permissions(
							player.user,
							send_messages_in_threads=False
						)
					else:
						await self.channel.set_permissions(
							player.user,
							send_messages=False
						)
					self.required_author = -1
					continue

				self.required_author = -1

				if isinstance(self.channel, discord.Thread):
					await self.bot.get_channel(self.channel.parent_id).set_permissions(
						player.user,
						send_messages_in_threads=False
					)
				else:
					await self.channel.set_permissions(
						player.user,
						send_messages=False
					)

				self.broadcast(f"{player.name}: {text}", player)
			elif isinstance(player.user, AIAbstraction):
				await self.channel.send(f"It's {player.user.name}'s turn to speak!")
				messages = self.context.setdefault(player.user, [])
				text = ""
				try:
					response = await self.client.chat.completions.create(
						model=player.user.model,
						messages=messages,
						max_tokens=100
					)
					text = self._clean_ai_content(response.choices[0].message.content or "")
				except Exception as exc:
					logger.exception("OpenAI completion failed for model %s during AI speech: %s", player.user.model, exc)
					text = ""

				if not text:
					await self.handle_player_failure(player)
					continue
				
				self.player_failures[player.user] = 0
				text = self._clean_ai_content(response.choices[0].message.content or "")

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
				next_speakers = await self.get_next_speaker(text, player)
				urgent_speakers = [p for p, level in next_speakers if level < 4]
				for p in urgent_speakers:
					if p in speaker_queue:
						speaker_queue.remove(p)
				speaker_queue = urgent_speakers + speaker_queue

	async def get_next_speaker(self, text: str, speaker: Player) -> list[tuple[Player, int]]:
		try:
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
- COUNTERCLAIM: A player roleclaims and someone needs to counterclaim
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
Message: "I'm the sheriff, I investigated DeepSeek last night and got Mafia. Vote her out."
Output: Claude:COUNTERCLAIM,DeepSeek:ACCUSED

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
{"\n  - ".join([p.name for p in self.participants if p.alive])}
Speaker: {speaker.name}
Message: '{text}'"""}
				],
				model=self.DISCUSSION_ANALYSER
			)
		except Exception as exc:
			logger.error("OpenAI completion failed for model %s during speaker analysis: %s", self.DISCUSSION_ANALYSER, exc)
			return []
		raw = response.choices[0].message.content.strip()

		alive_participants = [p for p in self.participants if p.alive]
		if not alive_participants:
			return []

		if raw == "NONE" or not raw:
			return []

		mentions = []
		for mention in raw.split(","):
			tags = mention.split(":")
			try:
				mentions.append({"name": tags[0].strip(), "level": ["COUNTERCLAIM", "ACCUSED", "ROLE", "ASKED", "CASUAL"].index(tags[1].strip())})
			except (IndexError, ValueError):
				continue

		mentions.sort(key=lambda x: x["level"])
		next_players = []
		for m in mentions:
			p = self._candidate_by_name(alive_participants, m["name"])
			if p and p != speaker and not any(np[0] == p for np in next_players):
				next_players.append((p, m["level"]))
				
		return next_players

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

		async def get_ai_vote(ai_player: Player):
			prompt = "\n".join([
				message,
				"Vote by replying with EXACTLY ONE line containing EXACTLY ONE of the option names below.",
				"Do not add punctuation, quotes, explanations, or multiple lines.",
				"OPTIONS:",
				options_block
			])

			self.context.setdefault(ai_player.user, []).append({
				"role": "user",
				"content": prompt
			})

			try:
				response = await asyncio.wait_for(
					self.client.chat.completions.create(
						model=ai_player.user.model,
						messages=self.context[ai_player.user]
					),
					timeout=min(timeout_s, 60.0)
				)
				content = self._clean_ai_content(response.choices[0].message.content or "")
				choice = self.extract_choice(content, candidate_names)
				
				if not choice:
					choice = random.choice(candidate_names)
				
				self.player_failures[ai_player.user] = 0
			except Exception as exc:
				logger.exception("AI vote failed for %s: %s", ai_player.name, exc)
				choice = random.choice(candidate_names)
				self.context[ai_player.user].append({"role": "assistant", "content": choice})
				return ai_player, choice

			self.context[ai_player.user].append({"role": "assistant", "content": choice})
			return ai_player, choice

		ai_players = [p for p in self.participants if isinstance(p.user, AIAbstraction)]
		human_voters = [p.user for p in self.participants if isinstance(p.user, discord.Member)]
		expected_human_votes = len(human_voters)

		async def ai_voting_manager():
			if not ai_players:
				return

			tasks = [get_ai_vote(p) for p in ai_players]
			for completed in asyncio.as_completed(tasks):
				ai_player, choice = await completed
				if choice:
					votes[hash(ai_player.name)] = choice
					tally = self._format_vote_details(votes, candidates, voter_names, allow_abstain)
					try:
						await poll.edit(content=base_message + "\n\n**Votes:**\n" + tally, view=view)
					except Exception:
						pass

		async def wait_for_human_votes():
			start = asyncio.get_event_loop().time()
			while True:
				got_human = sum(1 for uid in votes.keys() if uid in view.allowed_voters)
				if got_human >= expected_human_votes:
					return
				if (asyncio.get_event_loop().time() - start) >= timeout_s:
					return
				await asyncio.sleep(1.0)

		await asyncio.gather(ai_voting_manager(), wait_for_human_votes())

		for p in self.participants:
			if isinstance(p.user, discord.Member) and p.user.id in view.allowed_voters:
				if p.user.id not in votes:
					await self.handle_player_failure(p)
				else:
					self.player_failures[p.user] = 0

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

		content = ""
		try:
			response = await self.client.chat.completions.create(
				model=ai_player.user.model,
				messages=messages
			)
			content = self._clean_ai_content(response.choices[0].message.content or "")
		except Exception as exc:
			logger.exception("OpenAI completion failed for model %s during AI completion for %s: %s", ai_player.user.model, ai_player.name, exc)

		if not content:
			await self.handle_player_failure(ai_player)
			return ""

		# Reset failures on success
		self.player_failures[ai_player.user] = 0
		messages.append({"role": "assistant", "content": content})
		return content

	async def on_message(self, message: discord.Message):
		logger.debug(f"Got message '{message.content}' from {message.author.id}, required author is {self.required_author}.")
		if message.author.id == self.required_author and message.content:
			await self.message_queue.put(message)
