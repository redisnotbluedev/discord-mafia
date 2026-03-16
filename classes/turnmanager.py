"""Turn management for Mafia game discussions and votes.

This module contains TurnManager, the central type for advancing the
state of the game.  It orchestrates:

- **Discussion rounds**: speaker ordering with an LLM-driven priority queue
  that analyses each message to decide who should respond next.
- **Voting**: parallel AI + human voting via Discord select menus, with
  timeouts and automatic failure tracking (modkill after two failures).
- **AI context**: maintains per-AI-player chat history and sends completions
  via the OpenAI SDK.
- **Human turns**: grants and revokes Discord send-message permissions to
  enforce turn-taking for human players equivalent to AI players.
"""

from classes.player import Player, AIAbstraction
import discord, random, asyncio, logging, data, json, re
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class TurnManager:
	"""Manages turn-taking, AI completions, and voting for a single game.

	A TurnManager is created once per game by MafiaGame.run().  The game
	switches its channel and participant list between phases (e.g. main
	channel for day discussion, mafia thread for night kills) via
	set_channel() and set_participants().

	Key state:
		context: Per-AI-player OpenAI message history (system prompt +
			conversation).  Keyed by AIAbstraction instance, values are
			lists of message dicts.
		player_failures: Failure count per player.  Two failures = modkill.
		webhook: If configured, AI messages are sent via webhook (allowing
			custom name/avatar).  Otherwise they fall back to plain bold text.
		required_author: Discord user ID of the human whose turn it
			currently is, or -1 if no human turn is active.  Used by
			on_message() to filter incoming messages.
	"""
	def _clean_ai_content(self, content: str) -> str:
		"""Strip chain-of-thought <think> content from AI responses.

		Some models (notably DeepSeek R1) wrap internal reasoning in
		<think>...</think> tags.  This strips those blocks so only the
		public-facing text remains.

		Args:
			content: Raw completion text from the AI model.

		Returns:
			Cleaned text with think blocks removed and whitespace trimmed,
			or an empty string if content was falsy.
		"""
		if not content:
			return ""
		content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL | re.IGNORECASE)
		return content.strip()

	def __init__(self, participants: list[Player], channel: discord.TextChannel | discord.Thread, bot: discord.Client, client: AsyncOpenAI | None = None):
		"""Initialize the turn manager for a new game.

		Loads the channel's webhook URL from data.json (if configured during
		/setup) and builds initial AI context (system prompts) for every AI
		participant.

		Args:
			participants: All players in the game (human and AI).
			channel: The Discord channel to send messages in.
			bot: The Discord bot client, used for webhook construction and
				channel permission management.
			client: OpenAI-compatible async client.  Defaults to a new
				AsyncOpenAI() instance using OPENAI_API_KEY / OPENAI_BASE_URL
				from the environment.

		Side effects:
			Reads data.json (via data.load()) to look up the webhook URL.
			Reads models.json to get the discussion_analyser model name.
		"""
		self.participants = participants
		self.channel: discord.TextChannel | discord.Thread = channel
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

	async def handle_player_failure(self, player: Player, message: discord.Message | None = None):
		"""Record a player's failure to respond and apply escalating penalties.

		First failure: sends a warning to the channel (human players only;
		AI failures are silent).  Second consecutive failure: the player is
		modkilled (marked dead with death_reason='modkill').

		Args:
			player: The player who failed to respond.
			message: Optional Discord message to delete (e.g. the 'it's your
				turn' prompt).  Deletion errors are silently swallowed.

		Side effects:
			Increments player_failures[player.user].
			May set player.alive = False and player.death_reason.
			Broadcasts the failure/modkill message to all AI contexts.
		"""
		user = player.user
		self.player_failures[user] = self.player_failures.get(user, 0) + 1

		if message:
			try:
				await message.delete()
			except Exception:
				pass

		if self.player_failures[user] >= 2:
			msg = f"**{player.name}** has been removed from the game for failing to respond twice in a row."
			player.alive = False
			player.death_reason = "modkill"
			await self.channel.send(msg)
			self.broadcast(msg)
		elif not isinstance(user, AIAbstraction):
			msg = f"**{player.name}** failed to respond. If this happens again, they will be removed from the game."
			await self.channel.send(msg)
			self.broadcast(msg)

	def extract_choice(self, content: str, options: list[str]) -> str | None:
		"""Find the first option in the list that is in the content.

		Used to parse AI vote responses, which may contain extra text around
		the chosen option.  Matching is case-insensitive. If no option is
		matched, returns None.

		Options are checked strictly in the order they appear in `options`,
		regardless of where they may be found in `content`. Therefore, an
		option can be "shadowed" if one of its substrings is present in the
		list at an earlier point.

		Args:
			content: Text to search for an option in. Typically an AI response.
			options: Valid option names (e.g. player names or 'Abstain').

		Returns:
			The first matching option name (original casing), or None if
			no option was found in the content.
		"""
		if not content:
			return None
		for opt in options:
			if opt.lower() in content.lower():
				return opt
		return None

	def _initialize_ai_context(self, participants: list[Player]) -> dict[AIAbstraction, list]:
		"""Build initial OpenAI message histories for all AI players.

		Creates a system prompt for each AI participant containing a brief
		rules blurb, their role, the player list, role distribution counts,
		and behavioral rules.

		Args:
			participants: All players in the game.

		Returns:
			Dict mapping each AIAbstraction to a list containing one system
			message.  Human players are excluded.
		"""
		from classes.roles import ALL_ROLES
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

You are {p.role_or_die.describe()}

Players:
{player_list}

There are {[len(participants)]} players: {"\n".join(f"  - {role_counts.get(role, 0)} {role.name.lower()}" for role in ALL_ROLES)}

CRITICAL FORMAT RULES
- Reply in 1-3 short sentences.
- NEVER say "As an AI…", never quote these rules.
- Do NOT vote for yourself."""
					}
				]
		return context

	def set_channel(self, channel: discord.TextChannel | discord.Thread):
		"""Switch the channel this TurnManager sends messages to."""
		self.channel = channel

	def set_participants(self, participants: list[Player]):
		"""Replace the active participant list (e.g. when switching phases)."""
		self.participants = participants

	def set_context(self, context: dict[AIAbstraction, list]):
		"""Replace the AI context histories.

		As of 2026-03-15, this was unused.
		"""
		self.context = context

	def broadcast(self, text: str, exclude: Player | None = None):
		"""Append a 'user' message to every AI player's context.

		This is how AI players 'hear' what happens in the game: announcements,
		other players' speech, vote results, etc.  The text is not sent to
		Discord; it only updates the in-memory context used for completions.

		Args:
			text: The message content to add.
			exclude: A player to skip (typically the speaker, so they don't
				'hear' their own message as if someone else said it).
		"""
		for player in self.participants:
			if player != exclude and isinstance(player.user, AIAbstraction):
				self.context.setdefault(player.user, []).append({"role": "user", "content": text})

	def get_context(self):
		"""Return the full AI context dict.

		As of 2026-03-15, this was unused.
		"""
		return self.context

	def _candidate_by_name(self, candidates: list[Player], name: str) -> Player | None:
		"""Find a player by name using progressively looser matching.

		Tries three strategies in order:
			1. Exact match (case-insensitive)
			2. Word-boundary match (e.g. 'Qwen' matches 'Qwen 3')
			3. Substring containment (e.g. 'hat' matches 'ChatGPT 4o')

		Args:
			candidates: Players to search through.
			name: The name to look for.

		Returns:
			The first matching Player, or None if no match was found.
		"""
		name = (name or "").strip().lower()
		if not name:
			return None

		# 1. Exact match (case-insensitive)
		for c in candidates:
			if c.name.lower() == name:
				return c

		# 2. Word boundary match (e.g. "Qwen" matches "Qwen 3")
		for c in candidates:
			if re.search(rf'\b{re.escape(name)}\b', c.name.lower()):
				return c

		# 3. Simple inclusion
		for c in candidates:
			if name in c.name.lower():
				return c

		return None

	def _format_vote_details(self, votes: dict[int, str], candidates: list[Player], voter_names: dict[int, str], allow_abstain: bool = False) -> str:
		"""Format the current vote tally as a natural language string.

		Args:
			votes: Mapping of voter ID (user ID or name hash) to chosen name.
			candidates: The players being voted on.
			voter_names: Mapping of voter ID to display name.
			allow_abstain: If True, includes 'Abstain' votes in the output.

		Returns:
			A newline-separated string like
			'- PlayerName: Voter1, Voter2 (2)', or 'No votes yet.'
			if no votes have been cast.
		"""
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
		"""Run a discussion round where players take turns speaking.

		This is the core discussion loop, used for both day discussion (with
		LLM-driven speaker analysis) and mafia night chat (simple round-robin).

		Speaker selection varies by mode:
			analyse=False (night/mafia chat): simple round-robin through alive
				participants, shuffled at the start.
			analyse=True (day discussion): uses an LLM-based priority queue.
				After each speech, get_next_speaker() identifies mentioned
				players and assigns priority levels (COUNTERCLAIM > ACCUSED >
				ASKED > ROLE).  Players who haven't spoken yet get priority,
				and a monopoly penalty prevents any player from dominating.

		For human players, their send-message permission is temporarily
		granted, they get a 3-minute timeout, and permission is revoked
		afterward.  For AI players, a completion is requested via the
		OpenAI SDK.

		Args:
			analyse: If True, use LLM-based speaker ordering (day discussion).
				If False, use simple round-robin (mafia night chat).
			rounds: Number of speaking turns.  Defaults to
				int(alive_participants * 1.5).

		Side effects:
			Sends messages to Discord (speech, turn prompts).
			Grants/revokes channel permissions for human players.
			Updates AI contexts via broadcast().
			May modkill players who fail to respond.
		"""
		player: Player | None = None
		spoken = set()
		speech_counts = {}
		# list of (Player, priority_level, turn_added)
		speaker_queue: list[tuple[Player, int, int]] = []
		alive_participants = [p for p in self.participants if p.alive]

		if rounds is None:
			rounds = int(len(alive_participants) * 1.5)

		if not analyse:
			random.shuffle(self.participants)

		self.running = True
		_ = 0
		while _ < rounds:
			text = ""
			if not analyse:
				alive_participants = [p for p in self.participants if p.alive]
				if not alive_participants:
					break
				player = alive_participants[_ % len(alive_participants)]
			else:
				# Clean dead players from queue
				speaker_queue = [item for item in speaker_queue if item[0].alive]

				alive_participants = [p for p in self.participants if p.alive]
				min_speech = min((speech_counts.get(p, 0) for p in alive_participants), default=0)

				processed_queue = []
				for p, priority, added_at in speaker_queue:
					age = _ - added_at
					effective_priority = priority

					# Heavy penalty for monopolizing conversation
					effective_priority += (speech_counts.get(p, 0) - min_speech) * 2

					if age >= 4:
						effective_priority += 1
					processed_queue.append((p, priority, added_at, effective_priority))

				if processed_queue:
					processed_queue.sort(key=lambda x: (x[3], x[1], -x[2]))

				urgent_speaker = None
				unsung = [p for p in self.participants if p not in spoken and p.alive]

				if processed_queue:
					top_p, top_pri, top_added, top_eff = processed_queue[0]
					# Highly urgent, or player hasn't spoken significantly more than others
					if top_pri <= 1 or speech_counts.get(top_p, 0) <= min_speech + 1:
						urgent_speaker = processed_queue.pop(0)
						speaker_queue = [(p, pr, ad) for p, pr, ad, ef in processed_queue]
						player = urgent_speaker[0]

				if not urgent_speaker:
					if unsung:
						player = random.choice(unsung)
					else:
						if alive_participants:
							# Pick whoever has spoken the least, with a bit of randomness among ties
							alive_participants.sort(key=lambda p: (speech_counts.get(p, 0), random.random()))
							player = alive_participants[0]
						else:
							break

			if not player or not player.alive:
				continue

			if isinstance(player.user, discord.Member):
				timeout_at = int(__import__("time").time() + 180)
				status_msg = await self.channel.send(f"> {player.user.mention}, it's your turn to speak! Ends <t:{timeout_at}:R>.")
				if isinstance(self.channel, discord.Thread):
					channel = self.bot.get_channel(self.channel.parent_id)
					assert isinstance(channel, discord.TextChannel)
					await channel.set_permissions(
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
					# message_queue is defined in __init__ and populated in
					# on_message. required_author filters which messages
					# on_message will accept. If multiple messages somehow come
					# in before message_queue returns, this will just grab the
					# first one, and a subsequent message may be ascribed as
					# the _next_ player's message, which could be awkward.
					msg = await asyncio.wait_for(self.message_queue.get(), timeout=180.0)
					text = msg.content or ""
					self.player_failures[player.user] = 0
				except asyncio.TimeoutError:
					await self.handle_player_failure(player, status_msg)
					speaker_queue = [item for item in speaker_queue if item[0] != player]
					spoken.add(player)
					speech_counts[player] = speech_counts.get(player, 0) + 1
					if isinstance(self.channel, discord.Thread):
						channel = self.bot.get_channel(self.channel.parent_id)
						assert isinstance(channel, discord.TextChannel)
						await channel.set_permissions(
							player.user,
							send_messages_in_threads=None
						)
					else:
						await self.channel.set_permissions(
							player.user,
							send_messages=None
						)
					self.required_author = -1
					if not analyse:
						_ += 1
					continue

				self.required_author = -1

				if isinstance(self.channel, discord.Thread):
					channel = self.bot.get_channel(self.channel.parent_id)
					assert isinstance(channel, discord.TextChannel)
					await channel.set_permissions(
						player.user,
						send_messages_in_threads=None
					)
				else:
					await self.channel.set_permissions(
						player.user,
						send_messages=None
					)

				self.broadcast(f"{player.name}: {text}", player)
			elif isinstance(player.user, AIAbstraction):
				status_msg = await self.channel.send(f"It's {player.user.name}'s turn to speak!")
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
					await self.handle_player_failure(player, status_msg)
					speaker_queue = [item for item in speaker_queue if item[0] != player]
					spoken.add(player)
					speech_counts[player] = speech_counts.get(player, 0) + 1
					if not analyse:
						_ += 1
					continue

				self.player_failures[player.user] = 0

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
			speech_counts[player] = speech_counts.get(player, 0) + 1
			# Remove current speaker from queue if they were in it
			speaker_queue = [item for item in speaker_queue if item[0] != player]

			if analyse:
				# next_speakers is list[(Player, level)]
				next_speakers = await self.get_next_speaker(text, player)

				# Only take COUNTERCLAIM, ACCUSED, ASKED, ROLE (level < 4)
				new_mentions = [(p, level) for p, level in next_speakers if level < 4]

				for p, level in new_mentions:
					# Remove if already in queue (to refresh position/priority)
					speaker_queue = [item for item in speaker_queue if item[0] != p]
					# Store (Player, priority, current_turn)
					speaker_queue.append((p, level, _))

				# Initial sort to keep the list somewhat organized,
				# though we re-calculate effective priority when popping.
				speaker_queue.sort(key=lambda x: (x[1], -x[2]))

				# Limit queue size to keep conversation moving and avoid stale topics
				if len(speaker_queue) > 5:
					speaker_queue = speaker_queue[:5]

			_ += 1

	async def get_next_speaker(self, text: str, speaker: Player) -> list[tuple[Player, int]]:
		"""Use an LLM to identify which players were mentioned in a message.

		Despite the method name, this does not make any final determination of
		who speaks next.

		Sends the message text and list of alive players to the discussion
		analyser model, which returns a structured list of mentioned players
		and their priority levels.

		Priority levels (lower = more urgent):
			0 = COUNTERCLAIM (someone needs to counter a role claim)
			1 = ACCUSED (directly accused of being mafia)
			2 = ASKED (target of a question)
			3 = ROLE (mentioned in relation to a role)
			4 = CASUAL (mentioned in passing)

		Args:
			text: The message that was just spoken.
			speaker: The player who spoke (excluded from results).

		Returns:
			List of (Player, priority_level) tuples, sorted by priority.
			Empty list if the LLM returns NONE or an error occurs.
		"""
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
- COUNTERCLAIM: A player roleclaims and another player needs to counterclaim (Highest Priority)
- ACCUSED: Directly accused of being Mafia, lying, or acting suspicious
- ASKED: The TARGET of a question (e.g. "X, what do you think?")
- ROLE: Mentioned in relation to a specific role or claim
- CASUAL: Mentioned as the SUBJECT of a question or in passing (Lowest Priority)

RULES:
1. Only include players from the provided list.
2. If a role is mentioned (e.g. "the sheriff"), include the player who claimed that role if known.
3. The person being spoken TO (the target of a question) MUST be first in the list.
4. Distinguish between the target of a question (ASKED) and the subject of a question (CASUAL).
5. Include ALL players who should reasonably respond to this message.
6. If nobody is mentioned, return: NONE
7. Return ONLY the comma-separated list, no other text.

EXAMPLES:
(In this scenario, Claude is the sheriff, and Grok is speaking.)
Message: "I'm the sheriff, I investigated DeepSeek last night and got Mafia. Vote her out."
Output: Claude:COUNTERCLAIM,DeepSeek:ACCUSED

Message: "Qwen, what's your read on Gemini? She's defending GLM."
Output: Qwen:ASKED,Gemini:CASUAL,GLM:CASUAL

Message: "Kimi is definitely Mafia, she's been too quiet"
Output: Kimi:ACCUSED

Message: "I think the doctor saved themselves last night"
Output: Llama:ROLE

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
		choice = response.choices[0].message.content
		assert isinstance(choice, str)
		raw = choice.strip()

		alive_participants = [p for p in self.participants if p.alive]
		if not alive_participants:
			return []

		if raw == "NONE" or not raw:
			return []

		mentions = []
		for mention in raw.split(","):
			tags = mention.split(":")
			try:
				mentions.append({"name": tags[0].strip(), "level": ["COUNTERCLAIM", "ACCUSED", "ASKED", "ROLE", "CASUAL"].index(tags[1].strip())})
			except (IndexError, ValueError):
				continue

		mentions.sort(key=lambda x: x["level"])
		next_players = []
		for m in mentions:
			p = self._candidate_by_name(alive_participants, m["name"])
			if p and p != speaker and not any(np[0] == p for np in next_players):
				next_players.append((p, m["level"]))

		return next_players

	async def run_vote(self, candidates: list[Player], message, placeholder="Vote for a player...", emoji="🗳️", timeout_s=120.0, break_ties_random=False, allow_abstain=False, require_majority=False):
		"""Run a vote where all players (human + AI) vote in parallel.

		Human players vote via a Discord select menu (VoteView); AI players
		vote via LLM completions.  The vote tally is live-updated in a
		single Discord message as votes come in.

		Args:
			candidates: Players who can be voted for.
			message: Text displayed above the vote (e.g. 'Who should be eliminated?').
			placeholder: Placeholder text in the select menu.
			emoji: Emoji shown on the select menu.
			timeout_s: Seconds before voting closes.  AI votes are also
				capped at min(timeout_s, 60) to avoid blocking.
			break_ties_random: If True, randomly pick among tied winners.
			allow_abstain: If True, adds an 'Abstain' option.  If abstain
				votes tie or beat all other options, returns None.
			require_majority: If True, the winner must have >50%% of total
				participants to win.  Otherwise returns None.

		Returns:
			The Player who won the vote, or None if there was a tie (and
			break_ties_random is False), no votes, abstention won, or the
			majority threshold was not met.

		Side effects:
			Sends and edits a Discord message with the live vote tally.
			Updates AI contexts with vote prompts and responses.
			Tracks player failures for humans who don't vote in time.
		"""
		from classes.views import VoteView
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

			assert isinstance(ai_player.user, AIAbstraction)
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

		if require_majority:
			majority_threshold = len(self.participants) // 2 + 1
			if best < majority_threshold:
				return None

		return self._candidate_by_name(candidates, winners[0])

	async def create_ai_completion(self, ai_player: Player, prompt: str) -> str:
		"""Send a prompt to an AI player's model and return the response.

		Appends the prompt as a 'user' message to the player's context,
		requests a completion, and appends the response as an 'assistant'
		message.  Used for night actions (e.g. 'Who do you want to kill?').

		Args:
			ai_player: The AI player to prompt.
			prompt: The prompt text (e.g. a night action question).

		Returns:
			The cleaned response text, or an empty string if the completion
			failed or returned nothing (in which case handle_player_failure
			is called).

		Side effects:
			If no response is received, this calls `self.handle_player_failure`,
			which may modkill the player.
		"""
		assert isinstance(ai_player.user, AIAbstraction)
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
		"""Route an incoming Discord message to the queue consumed by run_round.

		Called by the bot's on_message handler.  If the message author
		matches required_author (set during a human turn in run_round),
		the message is placed on the queue for run_round to consume.
		Otherwise the message is silently ignored.
		"""
		logger.debug(f"Got message '{message.content}' from {message.author.id}, required author is {self.required_author}.")
		if message.author.id == self.required_author and message.content:
			await self.message_queue.put(message)
