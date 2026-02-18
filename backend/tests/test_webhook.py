"""Unit tests for webhook notification service."""
import pytest
from unittest.mock import patch, MagicMock


class TestSendWebhook:
    """Tests for send_webhook function."""

    @patch('app.config.get_settings')
    @patch('httpx.post')
    def test_sends_discord_embed(self, mock_post, mock_settings):
        """Test sending a Discord-compatible webhook."""
        from app.services.webhook import send_webhook

        mock_settings.return_value = MagicMock(webhook_url="https://discord.com/api/webhooks/test")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        send_webhook(title="Test", description="Hello", color=0xFF0000)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://discord.com/api/webhooks/test"
        payload = call_args[1]["json"]
        assert payload["embeds"][0]["title"] == "Test"
        assert payload["embeds"][0]["description"] == "Hello"
        assert payload["embeds"][0]["color"] == 0xFF0000

    @patch('app.config.get_settings')
    @patch('httpx.post')
    def test_skips_when_no_url(self, mock_post, mock_settings):
        """Test silently skips when webhook_url is empty."""
        from app.services.webhook import send_webhook

        mock_settings.return_value = MagicMock(webhook_url="")

        send_webhook(title="Test", description="Hello")

        mock_post.assert_not_called()

    @patch('app.config.get_settings')
    @patch('httpx.post')
    def test_skips_when_url_none(self, mock_post, mock_settings):
        """Test silently skips when webhook_url is None."""
        from app.services.webhook import send_webhook

        mock_settings.return_value = MagicMock(webhook_url=None)

        send_webhook(title="Test", description="Hello")

        mock_post.assert_not_called()

    @patch('app.config.get_settings')
    @patch('httpx.post')
    def test_does_not_raise_on_failure(self, mock_post, mock_settings):
        """Test that failures are logged but not raised."""
        from app.services.webhook import send_webhook

        mock_settings.return_value = MagicMock(webhook_url="https://example.com/webhook")
        mock_post.side_effect = Exception("Connection refused")

        # Should not raise
        send_webhook(title="Test", description="Hello")

    @patch('app.config.get_settings')
    @patch('httpx.post')
    def test_includes_fields(self, mock_post, mock_settings):
        """Test webhook with custom fields."""
        from app.services.webhook import send_webhook

        mock_settings.return_value = MagicMock(webhook_url="https://example.com/webhook")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        fields = [{"name": "Count", "value": "42", "inline": True}]
        send_webhook(title="Test", description="Hello", fields=fields)

        payload = mock_post.call_args[1]["json"]
        assert payload["embeds"][0]["fields"] == fields
