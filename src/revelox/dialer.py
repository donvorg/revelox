"""Twilio outbound call dialing."""

from __future__ import annotations

import os


class DialError(Exception):
    """Raised when dialing fails."""


def dial(from_number: str, to_number: str, voice_url: str) -> str:
    """Place an outbound call via the Twilio REST API.

    Args:
        from_number: Caller ID in E.164 format.
        to_number: Target phone number in E.164 format.
        voice_url: Public URL for Twilio to fetch TwiML from.

    Returns:
        The Twilio call SID.

    Raises:
        DialError: If credentials are missing or the API call fails.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        raise DialError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")

    try:
        from twilio.rest import Client
    except ImportError:
        raise DialError(
            "twilio is not installed. Install with: pip install 'revelox[twilio]'"
        ) from None

    client = Client(account_sid, auth_token)
    try:
        call = client.calls.create(to=to_number, from_=from_number, url=voice_url)
    except Exception as e:
        raise DialError(f"Twilio API error: {e}") from None

    return call.sid
