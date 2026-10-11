# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Chat provider backed by a running Ollama server (default model: llama3.1).
#
# Tool calling isn't implemented here (see base.py's docstring) — `tools` is
# accepted only so this stays interchangeable with OpenAILLMProvider; a turn
# routed through Ollama simply never gets offered the web_search tool.

import logging
from collections.abc import Iterator

import ollama

from app.core.config import settings
from app.providers.llm.base import LLMProvider, ToolCallRequest

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLMProvider):
    def __init__(self, model_name: str | None = None) -> None:
        self._model = model_name or settings.OLLAMA_CHAT_MODEL
        self._client = ollama.Client(host=settings.OLLAMA_BASE_URL)

    def stream_chat(
        self, messages: list[dict[str, str]], *, tools: list[dict] | None = None
    ) -> Iterator[str | list[ToolCallRequest]]:
        if tools:
            logger.debug("OllamaLLMProvider ignores tools (tool calling not implemented for it)")
        stream = self._client.chat(model=self._model, messages=messages, stream=True)
        for chunk in stream:
            content = chunk.message.content
            if content:
                yield content
