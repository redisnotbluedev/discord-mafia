import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import logging
import asyncio
import discord
from discord import Webhook, Embed, Colour

from logging_utils import WebhookLoggingHandler


class TestWebhookLoggingHandlerInit:
    def test_init_stores_webhook(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        assert handler.webhook is webhook

    def test_init_sets_level(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook, level=logging.WARNING)
        assert handler.level == logging.WARNING

    def test_init_default_level_is_notset(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        assert handler.level == logging.NOTSET

    def test_init_sets_formatter(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        assert handler.formatter is not None
        assert isinstance(handler.formatter, logging.Formatter)

    def test_init_formatter_format_string(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        formatted = handler.formatter.format(record)
        assert formatted == "test message"


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
class TestWebhookLoggingHandlerEmit:
    def test_emit_filters_discord_webhook_logger(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="discord.webhook", level=logging.INFO, pathname="", lineno=0,
            msg="webhook message", args=(), exc_info=None
        )
        
        with patch("asyncio.create_task") as mock_create_task:
            handler.emit(record)
            mock_create_task.assert_not_called()

    def test_emit_filters_discord_webhook_sublogger(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="discord.webhook.something", level=logging.INFO, pathname="", lineno=0,
            msg="webhook message", args=(), exc_info=None
        )
        
        with patch("asyncio.create_task") as mock_create_task:
            handler.emit(record)
            mock_create_task.assert_not_called()

    def test_emit_calls_create_task_for_valid_record(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        
        with patch("asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = None
            handler.emit(record)
            mock_create_task.assert_called_once()
            coro = mock_create_task.call_args[0][0]
            coro.close()

    def test_emit_catches_exception_from_create_task(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        
        with patch("asyncio.create_task", side_effect=RuntimeError("No event loop")):
            with patch("builtins.print") as mock_print:
                handler.emit(record)
                mock_print.assert_called_once()
                assert "Failed to send log to webhook" in mock_print.call_args[0][0]

    def test_emit_does_not_filter_discord_logger_without_webhook_prefix(self):
        webhook = MagicMock(spec=Webhook)
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="discord.client", level=logging.INFO, pathname="", lineno=0,
            msg="client message", args=(), exc_info=None
        )
        
        with patch("asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = None
            handler.emit(record)
            mock_create_task.assert_called_once()
            coro = mock_create_task.call_args[0][0]
            coro.close()


class TestWebhookLoggingHandlerSendToWebhook:
    @pytest.mark.asyncio
    async def test_send_to_webhook_calls_webhook_send(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        webhook.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_webhook_creates_embed(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        call_args = webhook.send.call_args
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, Embed)

    @pytest.mark.asyncio
    async def test_send_to_webhook_debug_color(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.DEBUG, pathname="", lineno=0,
            msg="debug message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.colour == Colour.dark_grey()

    @pytest.mark.asyncio
    async def test_send_to_webhook_info_color(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="info message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.colour == Colour.blurple()

    @pytest.mark.asyncio
    async def test_send_to_webhook_warning_color(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.WARNING, pathname="", lineno=0,
            msg="warning message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.colour == Colour.orange()

    @pytest.mark.asyncio
    async def test_send_to_webhook_error_color(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.ERROR, pathname="", lineno=0,
            msg="error message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.colour == Colour.red()

    @pytest.mark.asyncio
    async def test_send_to_webhook_critical_color(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.CRITICAL, pathname="", lineno=0,
            msg="critical message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.colour == Colour.dark_red()

    @pytest.mark.asyncio
    async def test_send_to_webhook_embed_title(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.title == "Info"

    @pytest.mark.asyncio
    async def test_send_to_webhook_embed_description(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.description == "test message"

    @pytest.mark.asyncio
    async def test_send_to_webhook_includes_exc_text(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.ERROR, pathname="", lineno=0,
            msg="error message", args=(), exc_info=None
        )
        record.exc_text = "Traceback: ValueError"
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert "error message" in embed.description
        assert "Traceback: ValueError" in embed.description

    @pytest.mark.asyncio
    async def test_send_to_webhook_no_exc_text(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.ERROR, pathname="", lineno=0,
            msg="error message", args=(), exc_info=None
        )
        record.exc_text = None
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.description == "error message"

    @pytest.mark.asyncio
    async def test_send_to_webhook_catches_exception(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock(side_effect=RuntimeError("Send failed"))
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        
        with patch("builtins.print") as mock_print:
            await handler._send_to_webhook(record)
            mock_print.assert_called_once()
            assert "Webhook send failed" in mock_print.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_to_webhook_default_color_for_unknown_level(self):
        webhook = MagicMock(spec=Webhook)
        webhook.send = AsyncMock()
        handler = WebhookLoggingHandler(webhook)
        
        record = logging.LogRecord(
            name="myapp", level=99, pathname="", lineno=0,
            msg="unknown level message", args=(), exc_info=None
        )
        
        await handler._send_to_webhook(record)
        
        embed = webhook.send.call_args.kwargs["embed"]
        assert embed.colour == Colour.default()
