from typing import Optional


class DuckMindError(Exception):
    """Base exception for duckmind."""


class ChallengeError(DuckMindError):
    """Could not solve the JS proof-of-work challenge."""


class RatelimitError(DuckMindError):
    """HTTP 429 from the server."""


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
