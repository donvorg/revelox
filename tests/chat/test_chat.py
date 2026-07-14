"""Tests for the chat history context management module."""

from revelox.chat import ChatHistory, ChatMessage


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_create_message(self) -> None:
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"


class TestChatHistory:
    """Tests for ChatHistory."""

    def test_add_and_len(self) -> None:
        h = ChatHistory()
        assert len(h) == 0
        h.add("user", "hi")
        assert len(h) == 1

    def test_recent(self) -> None:
        h = ChatHistory()
        h.add("user", "a")
        h.add("assistant", "b")
        h.add("user", "c")
        assert [m.content for m in h.recent(2)] == ["b", "c"]

    def test_context_without_summary(self) -> None:
        h = ChatHistory()
        h.add("user", "a")
        h.add("assistant", "b")
        ctx = h.context(recent_n=10)
        assert len(ctx) == 2
        assert ctx[0].content == "a"

    def test_summarize_replaces_old_messages(self) -> None:
        h = ChatHistory()
        for i in range(15):
            h.add("user", f"msg-{i}")
        h.summarize(lambda msgs: f"summary of {len(msgs)} messages", keep_recent=5)
        assert len(h) == 5
        ctx = h.context(recent_n=5)
        assert len(ctx) == 6
        assert ctx[0].role == "system"
        assert "summary of 10 messages" in ctx[0].content
        assert ctx[1].content == "msg-10"

    def test_summarize_noop_when_few_messages(self) -> None:
        h = ChatHistory()
        h.add("user", "a")
        h.summarize(lambda msgs: "should not be called", keep_recent=5)
        ctx = h.context()
        assert len(ctx) == 1
        assert ctx[0].role == "user"

    def test_context_after_summarize(self) -> None:
        h = ChatHistory()
        for i in range(20):
            h.add("user", f"m{i}")
        h.summarize(lambda msgs: "old stuff", keep_recent=3)
        ctx = h.context(recent_n=3)
        assert ctx[0].content == "old stuff"
        assert [m.content for m in ctx[1:]] == ["m17", "m18", "m19"]
