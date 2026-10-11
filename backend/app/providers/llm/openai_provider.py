# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Chat provider backed by the OpenAI API (default model: gpt-4o-mini).

import logging
import socket
import time
from collections.abc import Iterator

from openai import OpenAI

from app.core.config import settings
from app.providers.llm.base import LLMProvider, ToolCallRequest

logger = logging.getLogger(__name__)

_OPENAI_HOST = "api.openai.com"


class OpenAILLMProvider(LLMProvider):
    def __init__(self, model_name: str | None = None) -> None:
        self._model = model_name or settings.OPENAI_CHAT_MODEL
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def stream_chat(
        self, messages: list[dict[str, str]], *, tools: list[dict] | None = None
    ) -> Iterator[str | list[ToolCallRequest]]:
        # Diagnostics for the intermittent "Connection error" seen from this
        # call — chat_service already logs the full exception+traceback on
        # failure, but that alone can't tell you *where* in the connection
        # the failure happened. A manual DNS resolution right before the
        # request, timed and logged either way, tells you whether a given
        # failure was "DNS never resolved" (this logs a WARNING) vs. resolved
        # fine but the request still failed further down the stack (TLS,
        # socket, proxy) — narrowing exactly what to chase next.
        dns_start = time.monotonic()
        try:
            resolved = socket.getaddrinfo(_OPENAI_HOST, 443)
            addresses = sorted({info[4][0] for info in resolved})
            logger.debug(
                "DNS resolved %s -> %s in %.3fs before OpenAI request (model=%s, messages=%d)",
                _OPENAI_HOST,
                addresses,
                time.monotonic() - dns_start,
                self._model,
                len(messages),
            )
        except OSError as exc:
            logger.warning(
                "DNS resolution for %s failed in %.3fs before OpenAI request: %s",
                _OPENAI_HOST,
                time.monotonic() - dns_start,
                exc,
            )

        request_start = time.monotonic()
        try:
            kwargs = {"model": self._model, "messages": messages, "stream": True}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            stream = self._client.chat.completions.create(**kwargs)
        except Exception:
            logger.warning(
                "OpenAI request failed after %.3fs (model=%s)",
                time.monotonic() - request_start,
                self._model,
                exc_info=True,
            )
            raise

        logger.debug(
            "OpenAI stream started after %.3fs (model=%s)",
            time.monotonic() - request_start,
            self._model,
        )

        # Tool-call fragments arrive spread across many chunks, indexed by
        # position (a model can request more than one call in the same
        # turn) — id/name usually land in the first fragment for that index,
        # arguments accumulate as a partial-JSON string across the rest.
        # Assembled but not yielded until the stream ends, since a caller
        # needs the complete arguments JSON, not a fragment of it.
        pending_calls: dict[int, dict[str, str]] = {}
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
            for tool_call in delta.tool_calls or []:
                entry = pending_calls.setdefault(tool_call.index, {"id": "", "name": "", "arguments": ""})
                if tool_call.id:
                    entry["id"] = tool_call.id
                if tool_call.function and tool_call.function.name:
                    entry["name"] = tool_call.function.name
                if tool_call.function and tool_call.function.arguments:
                    entry["arguments"] += tool_call.function.arguments

        if pending_calls:
            yield [
                ToolCallRequest(id=entry["id"], name=entry["name"], arguments=entry["arguments"])
                for entry in pending_calls.values()
            ]

    def request_tool_call(self, messages: list[dict[str, str]], tool: dict) -> ToolCallRequest | None:
        # Non-streaming on purpose: the caller (citation grounding) wants one
        # small structured JSON result, not a token stream, and forcing the
        # exact function via tool_choice means the model can't just answer
        # in prose instead of calling it.
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": tool["function"]["name"]}},
            )
        except Exception:
            logger.warning("OpenAI forced tool call request failed (model=%s)", self._model, exc_info=True)
            return None

        calls = response.choices[0].message.tool_calls or []
        if not calls:
            return None
        call = calls[0]
        return ToolCallRequest(id=call.id, name=call.function.name, arguments=call.function.arguments)
