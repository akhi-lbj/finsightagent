"""IFM K2 Horizon LiteLLM client wrapper for Google ADK.

Ensures:
1. OpenAI-compatible routing to https://api.ifm.ai/v1 with `IFM/K2-Horizon-375B-A23B`.
2. Per-run `X-Session-ID` header for vLLM consistent-hash KV cache affinity.
3. Configurable `chat_template_kwargs={"reasoning_effort": "high" | "medium"}`.
4. Verbatim `reasoning_content` replay on every assistant tool-call turn (even if `""`),
   as required by IFM K2 Horizon.
5. `output_schema_and_tools=False` capability so ADK never attempts to mix
   `output_schema` and external tool calling on the same agent.
6. Safe JSON normalization when `response_format` is active:
   - Never sets `drop_params=True` (so LiteLLM never silently drops `response_format` or
     `extra_body`).
   - If K2 Horizon occasionally emits reasoning preamble or markdown code fences around
     a JSON object in `content` (e.g., when a backend node skips separating `reasoning_content`),
     extracts the valid JSON object cleanly so ADK's Pydantic `output_schema` validator
     never crashes with `json_invalid`.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Literal

from dotenv import load_dotenv
from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.lite_llm import LiteLlm, LiteLLMClient
from pydantic import Field

load_dotenv()

DEFAULT_IFM_BASE_URL = "https://api.ifm.ai/v1"
DEFAULT_IFM_MODEL = "IFM/K2-Horizon-375B-A23B"

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _ensure_reasoning_content_on_assistant_turns(kwargs: dict[str, Any]) -> None:
    """Guarantees every assistant message with tool_calls carries `reasoning_content`."""
    messages = kwargs.get("messages")
    if not isinstance(messages, list):
        return
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            if msg.get("tool_calls") and (
                "reasoning_content" not in msg or msg.get("reasoning_content") is None
            ):
                msg["reasoning_content"] = ""


def _extract_json_object(text: str) -> str | None:
    """Extracts the last valid top-level JSON object from mixed reasoning/markdown text."""
    stripped = text.strip()
    if not stripped:
        return None

    # Fast path: already valid JSON
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return stripped
    except ValueError:
        pass

    # Check ```json ... ``` fenced blocks (prefer the last one, which is the final answer)
    fenced_matches = _FENCED_JSON_RE.findall(stripped)
    for candidate in reversed(fenced_matches):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return candidate
        except ValueError:
            continue

    # Fallback: scan for balanced JSON objects from the end of the string backwards
    decoder = json.JSONDecoder()
    starts = [i for i, ch in enumerate(stripped) if ch == "{"]
    for idx in reversed(starts):
        try:
            obj, _ = decoder.raw_decode(stripped, idx)
            if isinstance(obj, dict):
                return json.dumps(obj, ensure_ascii=False)
        except ValueError:
            continue

    return None


def _sanitize_structured_response(resp: Any, response_format: Any) -> Any:
    """Ensures `choice.message.content` is clean JSON when `response_format` was requested."""
    if not response_format:
        return resp
    choices = getattr(resp, "choices", None)
    if not choices:
        return resp
    msg = getattr(choices[0], "message", None)
    if msg is None:
        return resp
    content = getattr(msg, "content", None)
    if isinstance(content, str) and content.strip():
        extracted = _extract_json_object(content)
        if extracted is not None and extracted != content:
            msg.content = extracted
    return resp


def _is_empty_or_invalid_structured(resp: Any, response_format: Any) -> bool:
    """Returns True if a structured-output call returned empty or non-JSON content."""
    if not response_format:
        return False
    choices = getattr(resp, "choices", None)
    if not choices:
        return True
    msg = getattr(choices[0], "message", None)
    content = getattr(msg, "content", None) if msg is not None else None
    if not isinstance(content, str) or not content.strip():
        return True
    return _extract_json_object(content) is None


class K2HorizonLiteLLMClient(LiteLLMClient):
    """LiteLLMClient subclass enforcing IFM K2 Horizon reasoning_content replay & JSON reliability."""

    async def acompletion(self, model: str, messages: Any, tools: Any, **kwargs: Any):
        call_kwargs = dict(kwargs)
        call_kwargs["messages"] = messages
        _ensure_reasoning_content_on_assistant_turns(call_kwargs)
        messages_patched = call_kwargs.pop("messages")
        response_format = call_kwargs.get("response_format")

        resp = await super().acompletion(model, messages_patched, tools, **call_kwargs)
        resp = _sanitize_structured_response(resp, response_format)

        # Retry once if K2 Horizon exhausted its reasoning turn or emitted prose instead of JSON
        if _is_empty_or_invalid_structured(resp, response_format):
            retry_kwargs = dict(call_kwargs)
            retry_kwargs["extra_body"] = {
                "chat_template_kwargs": {"reasoning_effort": "low"}
            }
            resp = await super().acompletion(model, messages_patched, tools, **retry_kwargs)
            resp = _sanitize_structured_response(resp, response_format)

        return resp

    def completion(
        self, model: str, messages: Any, tools: Any, stream: bool = False, **kwargs: Any
    ):
        call_kwargs = dict(kwargs)
        call_kwargs["messages"] = messages
        _ensure_reasoning_content_on_assistant_turns(call_kwargs)
        messages_patched = call_kwargs.pop("messages")
        response_format = call_kwargs.get("response_format")

        resp = super().completion(model, messages_patched, tools, stream=stream, **call_kwargs)
        if not stream:
            resp = _sanitize_structured_response(resp, response_format)
            if _is_empty_or_invalid_structured(resp, response_format):
                retry_kwargs = dict(call_kwargs)
                retry_kwargs["extra_body"] = {
                    "chat_template_kwargs": {"reasoning_effort": "low"}
                }
                resp = super().completion(
                    model, messages_patched, tools, stream=stream, **retry_kwargs
                )
                resp = _sanitize_structured_response(resp, response_format)
        return resp


class K2HorizonLlm(LiteLlm):
    """Google ADK BaseLlm wrapper for IFM K2 Horizon."""

    llm_client: LiteLLMClient = Field(default_factory=K2HorizonLiteLLMClient, exclude=True)

    @property
    def capabilities(self) -> LlmCapabilities:
        # Enforce strict tool vs. output_schema separation on K2 Horizon.
        return LlmCapabilities(output_schema_and_tools=False)


def build_k2_model(
    *,
    session_id: str | None = None,
    reasoning_effort: Literal["low", "medium", "high"] = "high",
    max_tokens: int = 8192,
    temperature: float | None = None,
) -> K2HorizonLlm:
    """Factory that constructs a K2HorizonLlm pinned to a session ID and reasoning budget."""
    load_dotenv()
    resolved_session_id = session_id or f"finsight-{uuid.uuid4().hex[:12]}"
    api_base = (
        os.getenv("IFM_BASE_URL")
        or os.getenv("IFM_API_BASE")
        or DEFAULT_IFM_BASE_URL
    ).strip()
    api_key = (os.getenv("IFM_API_KEY") or "").strip()
    raw_model = (os.getenv("IFM_MODEL") or DEFAULT_IFM_MODEL).strip()
    litellm_model = raw_model if raw_model.startswith("openai/") else f"openai/{raw_model}"

    kwargs: dict[str, Any] = {
        "api_base": api_base,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "extra_headers": {"X-Session-ID": resolved_session_id},
        "extra_body": {
            "chat_template_kwargs": {"reasoning_effort": reasoning_effort},
        },
        "drop_params": False,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    return K2HorizonLlm(model=litellm_model, **kwargs)
