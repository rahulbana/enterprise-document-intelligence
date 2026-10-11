# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# No live OpenAI call or real DNS lookup is made in tests — both the client
# and socket.getaddrinfo are stubbed. Covers stream_chat's own behavior plus
# the diagnostic logging added around it (see openai_provider.py) for
# tracing the intermittent "Connection error" reports.

import logging
import socket
from dataclasses import dataclass, field

import pytest

from app.providers.llm import openai_provider as module
from app.providers.llm.base import ToolCallRequest
from app.providers.llm.openai_provider import OpenAILLMProvider


@dataclass
class FakeFunctionDelta:
    name: str | None = None
    arguments: str | None = None


@dataclass
class FakeToolCallDelta:
    index: int
    id: str | None = None
    function: FakeFunctionDelta | None = None


@dataclass
class FakeDelta:
    content: str | None = None
    tool_calls: list[FakeToolCallDelta] | None = None


@dataclass
class FakeChoice:
    delta: FakeDelta


@dataclass
class FakeChunk:
    choices: list[FakeChoice]


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunctionDelta


@dataclass
class FakeNonStreamMessage:
    tool_calls: list[FakeToolCall] | None = None


@dataclass
class FakeNonStreamChoice:
    message: FakeNonStreamMessage


@dataclass
class FakeNonStreamResponse:
    choices: list[FakeNonStreamChoice]


@dataclass
class FakeCompletionsResource:
    chunks: list[FakeChunk] = field(default_factory=list)
    error: Exception | None = None
    calls: list[dict] = field(default_factory=list)
    # Only used by request_tool_call (non-streaming) tests; stream_chat
    # tests never set this and always get the chunked `chunks` iterator.
    non_stream_response: FakeNonStreamResponse | None = None

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if kwargs.get("stream"):
            return iter(self.chunks)
        return self.non_stream_response


class FakeOpenAIClient:
    def __init__(self, completions: FakeCompletionsResource, api_key: str | None = None) -> None:
        self.chat = type("_Chat", (), {"completions": completions})()


def _fake_getaddrinfo_ok(*_args, **_kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.18.6.192", 443))]


def _fake_getaddrinfo_fails(*_args, **_kwargs):
    raise OSError(8, "nodename nor servname provided, or not known")


def test_stream_chat_yields_content_and_skips_empty_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = FakeCompletionsResource(
        chunks=[
            FakeChunk([FakeChoice(FakeDelta("Hel"))]),
            FakeChunk([FakeChoice(FakeDelta(None))]),
            FakeChunk([FakeChoice(FakeDelta("lo"))]),
        ]
    )
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()

    result = list(provider.stream_chat([{"role": "user", "content": "hi"}]))

    assert result == ["Hel", "lo"]
    assert completions.calls[0]["stream"] is True


def test_stream_chat_logs_dns_resolution_before_request(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    completions = FakeCompletionsResource(chunks=[])
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()

    with caplog.at_level(logging.DEBUG, logger=module.__name__):
        list(provider.stream_chat([{"role": "user", "content": "hi"}]))

    assert any("DNS resolved api.openai.com" in r.message for r in caplog.records)


def test_stream_chat_logs_warning_when_dns_resolution_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    completions = FakeCompletionsResource(chunks=[])
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_fails)
    provider = OpenAILLMProvider()

    with caplog.at_level(logging.DEBUG, logger=module.__name__):
        list(provider.stream_chat([{"role": "user", "content": "hi"}]))

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("DNS resolution for api.openai.com failed" in r.message for r in warnings)
    # A DNS failure here doesn't itself abort the call — the real request is
    # still attempted (and may still succeed via a cached/alternate route),
    # so this is a diagnostic signal, not a short-circuit.
    assert completions.calls


def test_stream_chat_logs_and_reraises_on_request_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    boom = ConnectionError("Connection error.")
    completions = FakeCompletionsResource(error=boom)
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()

    with caplog.at_level(logging.DEBUG, logger=module.__name__):
        with pytest.raises(ConnectionError):
            list(provider.stream_chat([{"role": "user", "content": "hi"}]))

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("OpenAI request failed" in r.message for r in warnings)


def test_stream_chat_omits_tools_kwargs_when_not_offered(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = FakeCompletionsResource(chunks=[])
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()

    list(provider.stream_chat([{"role": "user", "content": "hi"}]))

    assert "tools" not in completions.calls[0]
    assert "tool_choice" not in completions.calls[0]


def test_stream_chat_accumulates_tool_call_fragments_across_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A real OpenAI stream spreads one tool call's id/name/arguments across
    # several chunks, indexed by position — arguments arrive as partial-JSON
    # fragments that only parse once fully concatenated.
    completions = FakeCompletionsResource(
        chunks=[
            FakeChunk(
                [
                    FakeChoice(
                        FakeDelta(
                            tool_calls=[
                                FakeToolCallDelta(
                                    index=0,
                                    id="call_1",
                                    function=FakeFunctionDelta(name="web_search", arguments=""),
                                )
                            ]
                        )
                    )
                ]
            ),
            FakeChunk(
                [
                    FakeChoice(
                        FakeDelta(
                            tool_calls=[
                                FakeToolCallDelta(
                                    index=0, function=FakeFunctionDelta(arguments='{"query"')
                                )
                            ]
                        )
                    )
                ]
            ),
            FakeChunk(
                [
                    FakeChoice(
                        FakeDelta(
                            tool_calls=[
                                FakeToolCallDelta(
                                    index=0, function=FakeFunctionDelta(arguments=': "hi"}')
                                )
                            ]
                        )
                    )
                ]
            ),
        ]
    )
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()
    tools = [{"type": "function", "function": {"name": "web_search"}}]

    result = list(provider.stream_chat([{"role": "user", "content": "hi"}], tools=tools))

    assert result == [[ToolCallRequest(id="call_1", name="web_search", arguments='{"query": "hi"}')]]
    assert completions.calls[0]["tools"] == tools
    assert completions.calls[0]["tool_choice"] == "auto"


def test_stream_chat_handles_multiple_tool_calls_in_one_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = FakeCompletionsResource(
        chunks=[
            FakeChunk(
                [
                    FakeChoice(
                        FakeDelta(
                            tool_calls=[
                                FakeToolCallDelta(
                                    index=0,
                                    id="call_1",
                                    function=FakeFunctionDelta(name="web_search", arguments="{}"),
                                ),
                                FakeToolCallDelta(
                                    index=1,
                                    id="call_2",
                                    function=FakeFunctionDelta(name="web_search", arguments="{}"),
                                ),
                            ]
                        )
                    )
                ]
            ),
        ]
    )
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()

    result = list(
        provider.stream_chat(
            [{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {"name": "web_search"}}],
        )
    )

    assert len(result) == 1
    assert {tc.id for tc in result[0]} == {"call_1", "call_2"}


def test_request_tool_call_forces_the_named_tool_and_is_not_streamed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = FakeCompletionsResource(
        non_stream_response=FakeNonStreamResponse(
            choices=[
                FakeNonStreamChoice(
                    FakeNonStreamMessage(
                        tool_calls=[
                            FakeToolCall(
                                id="ground_1",
                                function=FakeFunctionDelta(
                                    name="cite_sources", arguments='{"used_source_numbers": [1]}'
                                ),
                            )
                        ]
                    )
                )
            ]
        )
    )
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()
    tool = {"type": "function", "function": {"name": "cite_sources"}}

    result = provider.request_tool_call([{"role": "user", "content": "check this"}], tool)

    assert result == ToolCallRequest(
        id="ground_1", name="cite_sources", arguments='{"used_source_numbers": [1]}'
    )
    assert "stream" not in completions.calls[0] or completions.calls[0]["stream"] is not True
    assert completions.calls[0]["tools"] == [tool]
    assert completions.calls[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "cite_sources"},
    }


def test_request_tool_call_returns_none_when_model_does_not_call_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completions = FakeCompletionsResource(
        non_stream_response=FakeNonStreamResponse(
            choices=[FakeNonStreamChoice(FakeNonStreamMessage(tool_calls=None))]
        )
    )
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()
    tool = {"type": "function", "function": {"name": "cite_sources"}}

    result = provider.request_tool_call([{"role": "user", "content": "check this"}], tool)

    assert result is None


def test_request_tool_call_returns_none_on_request_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    completions = FakeCompletionsResource(error=ConnectionError("boom"))
    monkeypatch.setattr(module, "OpenAI", lambda **_: FakeOpenAIClient(completions))
    monkeypatch.setattr(module.socket, "getaddrinfo", _fake_getaddrinfo_ok)
    provider = OpenAILLMProvider()
    tool = {"type": "function", "function": {"name": "cite_sources"}}

    with caplog.at_level(logging.WARNING, logger=module.__name__):
        result = provider.request_tool_call([{"role": "user", "content": "check this"}], tool)

    assert result is None
    assert any("forced tool call" in r.message for r in caplog.records)
