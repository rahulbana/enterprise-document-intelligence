# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# LLMProvider interface. messages follow the OpenAI chat-message shape
# ({"role": "system"|"user"|"assistant"|"tool", "content": str}) since both
# implementations either speak it natively (OpenAI) or accept it as-is
# (Ollama's chat API).
#
# Tool calling (Phase 12): stream_chat's `tools` param is the OpenAI
# function-calling tool schema (a list of {"type": "function", "function":
# {...}} dicts) — pass None for a plain no-tools turn. The stream mostly
# yields plain `str` content deltas exactly as before; the one addition is
# that if the model decides to call a tool instead of (or before) answering,
# the generator yields exactly one `list[ToolCallRequest]` — the fully
# assembled requests, only once the model has finished emitting them — with
# no content deltas for that same call. Callers distinguish the two with
# isinstance(). Only OpenAILLMProvider actually implements tool calling
# today; OllamaLLMProvider accepts (and ignores) `tools` so the interface
# stays uniform.
#
# request_tool_call (Phase 13, citation grounding): a separate, non-streaming
# escape hatch for when the caller needs exactly one forced tool call and
# nothing else — chat_service uses it after the answer is fully streamed, to
# ask "which of these sources did you actually use" via a forced
# cite_sources call rather than parsing the model's own inline [1]/[2]
# markers out of free text. Default implementation returns None (no
# support); callers must treat that the same as "grounding unavailable" and
# degrade gracefully (e.g. keep every citation unfiltered) rather than fail
# the turn — same "optional, degrades to None" contract as
# providers/websearch's factory.

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCallRequest:
    id: str
    name: str
    arguments: str  # raw JSON string, exactly as the model emitted it


class LLMProvider(ABC):
    @abstractmethod
    def stream_chat(
        self, messages: list[dict[str, str]], *, tools: list[dict] | None = None
    ) -> Iterator[str | list[ToolCallRequest]]:
        """Yield response text deltas as they arrive from the model, or (see
        module docstring) a single list[ToolCallRequest] if the model calls
        a tool instead."""
        ...

    def request_tool_call(self, messages: list[dict[str, str]], tool: dict) -> ToolCallRequest | None:
        """Non-streaming call that forces the model to call `tool` (exactly
        that one, not "auto"). Returns None if the provider doesn't support
        forced tool calls, or if the model still didn't call it — either way
        the caller has no grounding data to work with."""
        return None
