"""FinSight ADK — Institutional Equity Research & Valuation Workbench (Streamlit UI)."""

from __future__ import annotations

import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.orchestrator import build_orchestrator_agent

load_dotenv()

st.set_page_config(
    page_title="FinSight ADK — Institutional Equity Research",
    page_icon="📊",
    layout="wide",
)

st.title("📊 FinSight ADK — Institutional Equity Research Workbench")
st.caption(
    "Powered by Google ADK (`AgentTool`, `SequentialAgent`, `LangchainTool`) · "
    "IFM K2 Horizon (`IFM/K2-Horizon-375B-A23B`) · Tavily Finance · yfinance · openpyxl"
)


def _format_event_step(event: Any) -> list[str]:
    """Formats ADK events into clean human-readable trace entries."""
    lines: list[str] = []
    author = getattr(event, "author", "system")
    content = getattr(event, "content", None)
    if not content or not getattr(content, "parts", None):
        return lines

    for part in content.parts:
        fc = getattr(part, "function_call", None)
        if fc is not None:
            arg_keys = ", ".join(list((fc.args or {}).keys())[:5])
            lines.append(f"🛠️ **`{author}`** → calling **`{fc.name}`**({arg_keys})")
        fr = getattr(part, "function_response", None)
        if fr is not None:
            resp = fr.response
            status = resp.get("status", "done") if isinstance(resp, dict) else "done"
            lines.append(f"✅ **`{fr.name}`** returned (`{status}`)")
    return lines


def _extract_final_markdown(event: Any, root_author: str = "InvestmentCommitteeLead") -> str:
    """Extracts non-thought text from the root orchestrator's response events."""
    if getattr(event, "author", None) != root_author:
        return ""
    content = getattr(event, "content", None)
    if not content or not getattr(content, "parts", None):
        return ""
    chunks: list[str] = []
    for part in content.parts:
        if getattr(part, "text", None) and not getattr(part, "thought", False):
            chunks.append(part.text)
    return "".join(chunks)


# ------------------------------------------------------------------------------
# Sidebar: Configuration & Inputs
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("Analysis Inputs")
    ticker = st.text_input(
        "Company Ticker (Yahoo Finance)",
        value="GESHIP.NS",
        placeholder="e.g., GESHIP.NS, SCI.NS, MAERSK-B.CO",
    )
    uploaded_pdf = st.file_uploader(
        "Upload Quarterly / Annual Filing (PDF)",
        type=["pdf"],
    )

    st.divider()
    st.subheader("Environment Status")
    has_ifm = bool(os.getenv("IFM_API_KEY"))
    has_tavily = bool(os.getenv("TAVILY_API_KEY"))
    st.write(f"IFM API Key: {'✅ Configured' if has_ifm else '❌ Missing (`IFM_API_KEY`)'}")
    st.write(f"Tavily API Key: {'✅ Configured' if has_tavily else '❌ Missing (`TAVILY_API_KEY`)'}")

    run_btn = st.button(
        "🚀 Run Investment Committee Analysis",
        type="primary",
        use_container_width=True,
        disabled=not (ticker.strip() and uploaded_pdf is not None),
    )

# ------------------------------------------------------------------------------
# Main Execution Flow
# ------------------------------------------------------------------------------
if run_btn and uploaded_pdf is not None:
    if not os.getenv("IFM_API_KEY"):
        st.error("`IFM_API_KEY` is not set in `.env`. Please configure it before running.")
        st.stop()
    if not os.getenv("TAVILY_API_KEY"):
        st.warning("`TAVILY_API_KEY` is not set in `.env`. Live Tavily web research may fail.")

    run_id = uuid.uuid4().hex[:10]
    session_id = f"finsight-{run_id}"
    work_dir = Path(tempfile.gettempdir()) / "finsight_adk" / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = work_dir / uploaded_pdf.name
    pdf_path.write_bytes(uploaded_pdf.getvalue())
    safe_ticker = "".join(c if c.isalnum() or c in "-_" else "_" for c in ticker.strip())
    excel_output_path = work_dir / f"{safe_ticker}_FinSight_Model.xlsx"

    col_trace, col_memo = st.columns([1, 2], gap="large")
    with col_trace:
        st.subheader("Live Agent Trace")
        trace_placeholder = st.empty()
    with col_memo:
        st.subheader("Investment Committee Memo")
        memo_placeholder = st.empty()

    trace_logs: list[str] = [f"🔑 Session ID: `{session_id}` (KV-cache affinity enabled)"]
    memo_chunks: list[str] = []
    start_time = time.perf_counter()

    with st.spinner("Running FinSight ADK multi-agent pipeline..."):
        orchestrator = build_orchestrator_agent(session_id=session_id)
        runner = InMemoryRunner(agent=orchestrator, app_name="finsight_adk")
        runner.auto_create_session = True

        user_prompt = (
            f"Run a complete institutional Investment Committee analysis for ticker `{ticker.strip()}`.\n"
            f"- Uploaded financial filing PDF path: `{pdf_path}`\n"
            f"- Target Excel financial model output path: `{excel_output_path}`\n\n"
            "Follow all 6 workflow steps: parse the PDF, fetch live market multiples, extract the "
            "normalized FinancialSnapshot, run QuantValuationAgent and QualitativeDiligenceTeam, "
            "build the 3-tab formula-driven Excel model at the target output path, and produce the "
            "final Markdown Investment Committee Memo."
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)],
        )

        try:
            for event in runner.run(
                user_id="ic_analyst",
                session_id=session_id,
                new_message=user_message,
            ):
                new_steps = _format_event_step(event)
                if new_steps:
                    trace_logs.extend(new_steps)
                    trace_placeholder.markdown("\n\n".join(trace_logs))

                chunk = _extract_final_markdown(event)
                if chunk:
                    memo_chunks.append(chunk)
                    memo_placeholder.markdown("".join(memo_chunks))
        except Exception as exc:
            st.error(f"Pipeline execution error: {exc}")

    elapsed = time.perf_counter() - start_time
    trace_logs.append(f"⏱️ Completed in **{elapsed:.1f}s**")
    trace_placeholder.markdown("\n\n".join(trace_logs))

    final_memo = "".join(memo_chunks).strip()
    if final_memo:
        memo_placeholder.markdown(final_memo)

    if excel_output_path.exists():
        st.success(f"Formula-driven Excel model ready: `{excel_output_path.name}`")
        st.download_button(
            label="📥 Download 3-Tab Excel Financial Model (.xlsx)",
            data=excel_output_path.read_bytes(),
            file_name=excel_output_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    else:
        st.warning("Excel model file was not created during this run. Check the agent trace for details.")
else:
    st.info(
        "Enter a Yahoo Finance ticker and upload a quarterly or annual PDF filing in the sidebar "
        "to launch the FinSight ADK Investment Committee pipeline."
    )
