from classes.player import Player, AIAbstraction
from classes.views import VoteView
import discord, openai, random, asyncio, logging, data

logger = logging.getLogger(__name__)

class TurnManager:
	def __init__(self, participants: list[Player], channel: discord.abc.Messageable, bot: discord.Client, client: openai.OpenAI = None, context: dict[AIAbstraction, list] = {}):
		self.participants = participants
		self.channel = channel
		self.client = client or openai.OpenAI()
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
		self.context: dict[AIAbstraction, list] = context

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
				await self.channel.set_permissions(
					player.user,
					send_messages=True
				)

				self.required_author = player.user.id
				logger.info("Waiting for message send")
				message = await self.message_queue.get()
				self.required_author = -1
				self.broadcast(f"{player.name} said: {message.content}")
				await self.channel.set_permissions(
					player.user,
					send_messages=False
				)

			elif isinstance(player.user, AIAbstraction):
				messages = self.context.setdefault(player.user, [])
				response = self.client.chat.completions.create(
					model=player.user.model,
					messages=messages
				)
				text = response.choices[0].message.content

				if self.webhook:
					await self.webhook.send(
						username=player.name,
						avatar_url=player.user.avatar,
						content=text
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

		for p in self.participants:
			if not isinstance(p.user, AIAbstraction):
				continue

			messages = self.context.setdefault(p.user, [])
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

			response = self.client.chat.completions.create(
				model=p.user.model,
				messages=messages
			)
			choice = (response.choices[0].message.content or "").strip()

			if choice not in candidate_names:
				choice = random.choice(candidate_names)

			votes[hash(p.name)] = choice

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
		if message.author.id == self.required_author and message.content:
			self.message_queue.put_nowait(message)
