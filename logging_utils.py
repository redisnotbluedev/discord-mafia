import asyncio, logging
from discord import Webhook, Embed, Colour

class WebhookLoggingHandler(logging.Handler):
	def __init__(self, webhook: Webhook, level=logging.NOTSET):
		super().__init__(level)
		self.webhook = webhook

	def emit(self, record):
		try:
			asyncio.create_task(self._send_to_webhook(record))
		except Exception as e:
			print(f"Failed to send log to webhook: {e}")

	async def _send_to_webhook(self, record: logging.LogRecord):
		try:
			await self.webhook.send(embed=Embed(
				colour={logging.DEBUG: Colour.dark_grey(), logging.INFO: Colour.blurple(), logging.WARNING: Colour.orange(), logging.ERROR: Colour.red(), logging.CRITICAL: Colour.dark_red()}.get(record.levelno, Colour.default()),
				title=record.levelname.title(),
				description=record.getMessage() + f"\n-# <t:{record.created}:f>"
			))
		except Exception as e:
			print(f"Webhook send failed: {e}")
