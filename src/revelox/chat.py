"""Chat history with summarize-and-recent context management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Callable


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["user", "assistant", "system"]
    content: str


class ChatHistory:
    """Manages conversation context with a summarize-and-recent strategy."""

    def __init__(self) -> None:
        """Initialize an empty chat history."""
        self._messages: list[ChatMessage] = []
        self._summary: ChatMessage | None = None

    def add(self, role: Literal["user", "assistant", "system"], content: str) -> None:
        """Append a message to the history."""
        self._messages.append(ChatMessage(role=role, content=content))

    def recent(self, n: int) -> list[ChatMessage]:
        """Return the last *n* messages."""
        if n < 0:
            raise ValueError("n must be non-negative")
        if n == 0:
            return []
        return self._messages[-n:]

    def summarize(
        self,
        summarizer: Callable[[list[ChatMessage]], str],
        keep_recent: int = 10,
    ) -> None:
        """Compress older messages into a summary.

        Args:
            summarizer: Callable that takes a list of messages and returns a summary string.
            keep_recent: Number of recent messages to keep verbatim.
        """
        if keep_recent < 0:
            raise ValueError("keep_recent must be non-negative")
        if len(self._messages) <= keep_recent:
            return
        old = self._messages[:-keep_recent] if keep_recent > 0 else list(self._messages)
        to_summarize: list[ChatMessage] = []
        if self._summary:
            to_summarize.append(self._summary)
        to_summarize.extend(old)
        summary_text = summarizer(to_summarize)
        self._messages = self._messages[-keep_recent:] if keep_recent > 0 else []
        self._summary = ChatMessage(role="system", content=summary_text)

    def context(self, recent_n: int = 10) -> list[ChatMessage]:
        """Return the optimal context window for an LLM call."""
        msgs = self.recent(recent_n)
        if self._summary:
            return [self._summary, *msgs]
        return msgs

    def __len__(self) -> int:
        """Return the total number of messages."""
        return len(self._messages)
