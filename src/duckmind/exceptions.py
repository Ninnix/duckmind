from typing import Optional
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


class DuckMindError(Exception):
    """Base exception for duckmind."""


class ChallengeError(DuckMindError):
    """Could not solve the JS proof-of-work challenge."""


class RatelimitError(DuckMindError):
    """HTTP 429 from the server."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = None
        if retry_after is not None:
            try:
                self.retry_after = max(0.0, float(retry_after))
            except (TypeError, ValueError):
                try:
                    date = parsedate_to_datetime(retry_after)
                    self.retry_after = max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    pass


class ConversationLimitError(DuckMindError):
    """Too many turns in one session."""


class APIError(DuckMindError):
    """Any other non-200 response."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        body: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
