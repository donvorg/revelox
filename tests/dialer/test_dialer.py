"""Tests for the Twilio dialer module."""

from unittest.mock import MagicMock, patch

import pytest

from revelox.dialer import DialError, dial


class TestDial:
    """Tests for the dial function."""

    def test_missing_account_sid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        with pytest.raises(DialError, match="TWILIO_ACCOUNT_SID"):
            dial("+15551234567", "+15559876543", "https://example.com/voice")

    def test_missing_auth_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        with pytest.raises(DialError, match="TWILIO_ACCOUNT_SID"):
            dial("+15551234567", "+15559876543", "https://example.com/voice")

    @patch("revelox.dialer.Client" if False else "twilio.rest.Client")
    def test_successful_dial(
        self, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token123")
        mock_call = MagicMock()
        mock_call.sid = "CA_test_sid"
        mock_client_cls.return_value.calls.create.return_value = mock_call

        sid = dial("+15551234567", "+15559876543", "https://example.com/voice")
        assert sid == "CA_test_sid"
        mock_client_cls.return_value.calls.create.assert_called_once_with(
            to="+15559876543",
            from_="+15551234567",
            url="https://example.com/voice",
        )

    @patch("twilio.rest.Client")
    def test_api_error_wraps_in_dial_error(
        self, mock_client_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token123")
        mock_client_cls.return_value.calls.create.side_effect = RuntimeError("boom")

        with pytest.raises(DialError, match="Twilio API error.*boom"):
            dial("+15551234567", "+15559876543", "https://example.com/voice")
