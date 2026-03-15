"""Discord webhook-based log handler.

Sends Python log records to a Discord webhook as color-coded embeds.
Used when LOG_WEBHOOK_URL is configured in the environment.
"""

import asyncio, logging
from discord import Webhook, Embed, Colour

class WebhookLoggingHandler(logging.Handler):
	"""Logging handler that sends records to a Discord webhook as embeds.

	Each log level gets a distinct color.  Filters out discord.webhook
	logger to prevent infinite recursion.

	Note: Uses asyncio.create_task(), so it only works if an event
	loop is already running.  Failures are printed to stdout.
	"""

	def __init__(self, webhook: Webhook, level=logging.NOTSET):
		super().__init__(level)
		self.webhook = webhook
		self.setFormatter(logging.Formatter("%(message)s"))

	def emit(self, record: logging.LogRecord):
		"""Log a record to the webhook, in the background."""
		if record.name.startswith("discord.webhook"):
			return
		try:
			asyncio.create_task(self._send_to_webhook(record))
		except Exception as e:
			print(f"Failed to send log to webhook: {e}")

	async def _send_to_webhook(self, record: logging.LogRecord):
		"""Await sending a log record to the webhook."""
		try:
			await self.webhook.send(embed=Embed(
				colour={logging.DEBUG: Colour.dark_grey(), logging.INFO: Colour.blurple(), logging.WARNING: Colour.orange(), logging.ERROR: Colour.red(), logging.CRITICAL: Colour.dark_red()}.get(record.levelno, Colour.default()),
				title=record.levelname.title(),
				description=self.format(record) + (f"\n{record.exc_text}" if record.exc_text else "")
			))
		except Exception as e:
			print(f"Webhook send failed: {e}")
