"""ADK Web `root_agent` definition for FinSight ADK.

Supports both:
- Passing a local PDF file path in the chat message, OR
- Attaching/uploading a PDF directly inside the `adk web` chat UI:
  `before_agent_callback` saves the PDF bytes to disk AND `before_model_callback`
  strips binary PDF `inline_data` parts from the outgoing `LlmRequest` so ADK's
  LiteLLM adapter does NOT attempt to call OpenAI's `/v1/files` upload endpoint
  (which returns 404 NotFoundError on IFM K2 Horizon). Instead, the orchestrator
  reads the saved PDF deterministically via `parse_financial_pdf(file_path=...)`.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# Ensure project root is importable regardless of working directory when `adk web` loads this module.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

from agents.orchestrator import build_orchestrator_agent  # noqa: E402


def _is_pdf_part(part: types.Part) -> bool:
    """Returns True if a genai Part carries inline binary PDF data."""
    inline = getattr(part, "inline_data", None)
    if not inline or not inline.data:
        return False
    mime = (inline.mime_type or "").lower()
    display_name = (getattr(inline, "display_name", "") or "").lower()
    return mime == "application/pdf" or display_name.endswith(".pdf")


def _save_pdf_part(part: types.Part, idx: int) -> Path:
    """Writes an inline PDF part to a temp directory and returns its saved Path."""
    upload_dir = Path(tempfile.gettempdir()) / "finsight_adk_web"
    upload_dir.mkdir(parents=True, exist_ok=True)
    inline = part.inline_data
    raw_name = getattr(inline, "display_name", None) or f"uploaded_filing_{idx}.pdf"
    safe_name = os.path.basename(raw_name)
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    saved_path = upload_dir / safe_name
    saved_path.write_bytes(inline.data)
    return saved_path


async def _capture_uploaded_pdf_callback(callback_context: CallbackContext) -> None:
    """Saves any PDF uploaded via the `adk web` attachment button to disk and records its path."""
    user_content: types.Content | None = getattr(callback_context, "user_content", None)
    if not user_content or not user_content.parts:
        return

    for idx, part in enumerate(list(user_content.parts)):
        if _is_pdf_part(part):
            saved_path = _save_pdf_part(part, idx)
            callback_context.state["uploaded_pdf_path"] = str(saved_path)


async def _strip_pdf_binary_before_model(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> LlmResponse | None:
    """Replaces binary PDF inline_data parts with a text pointer to the saved local path.

    Prevents ADK's LiteLLM adapter from calling `litellm.acreate_file` (`POST /v1/files`),
    which fails with HTTP 404 NotFoundError on OpenAI-compatible inference servers like
    IFM K2 Horizon (`https://api.ifm.ai/v1`).
    """
    if not llm_request.contents:
        return None

    saved_path_str = callback_context.state.get("uploaded_pdf_path")

    for content in llm_request.contents:
        if not content.parts:
            continue
        new_parts: list[types.Part] = []
        for idx, part in enumerate(content.parts):
            if _is_pdf_part(part):
                # Ensure the PDF is saved even if it came from an earlier session turn
                local_path = Path(saved_path_str) if saved_path_str else _save_pdf_part(part, idx)
                if not local_path.exists():
                    local_path = _save_pdf_part(part, idx)
                callback_context.state["uploaded_pdf_path"] = str(local_path)
                new_parts.append(
                    types.Part.from_text(
                        text=(
                            f"[Attached PDF saved locally at `{local_path}`. "
                            f"Call `parse_financial_pdf(file_path=r'{local_path}')` to read it.]"
                        )
                    )
                )
            else:
                new_parts.append(part)
        content.parts = new_parts

    return None


root_agent = build_orchestrator_agent()
root_agent.before_agent_callback = _capture_uploaded_pdf_callback
root_agent.before_model_callback = _strip_pdf_binary_before_model
