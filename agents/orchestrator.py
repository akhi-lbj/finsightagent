"""Agent 1: InvestmentCommitteeLead (Root Orchestrator LlmAgent)."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, FunctionTool

from agents.extractor_agent import build_financial_extractor_agent
from agents.qual_agent import build_qualitative_diligence_team
from agents.quant_agent import build_quant_valuation_agent
from llm_client import build_k2_model
from tools.excel_builder import build_excel_model
from tools.market_data import fetch_market_multiples
from tools.pdf_parser import parse_financial_pdf

_ORCHESTRATOR_INSTRUCTION = """You are the `InvestmentCommitteeLead`, a Senior Investment Analyst running
the **FinSight ADK** institutional equity research workflow.

Given a company ticker, a path to an uploaded quarterly/annual PDF filing, and a desired Excel
output path, execute the following 6-step workflow strictly in order:

1. **Extract PDF Filing:** Call `parse_financial_pdf(file_path=...)` to extract financial tables
   (Markdown) and MD&A narrative text.
2. **Pull Live Market Data:** Call `fetch_market_multiples(ticker=...)` to fetch live Yahoo Finance
   share price, market cap, enterprise value, and valuation multiples.
3. **Normalize Financial Snapshot:** Call the `FinancialExtractorAgent` tool, passing the extracted
   PDF tables, MD&A text, ticker, and live Yahoo Finance metrics so it returns a validated
   `FinancialSnapshot` JSON object.
4. **Run Quantitative Valuation & Qualitative Diligence:**
   - Call the `QuantValuationAgent` tool with the exact `FinancialSnapshot` JSON fields to obtain
     the `ValuationModel` JSON object (ratios + Bear/Base/Bull scenarios).
   - Call the `QualitativeDiligenceTeam` tool with the company name, ticker, reporting period,
     sector/industry context, and `management_commentary_summary` so it executes live Tavily web
     research and returns the `QualitativeDiligence` JSON object.
5. **Build Institutional Excel Model:** Call `build_excel_model(snapshot=..., valuation=..., output_path=...)`
   passing the full `FinancialSnapshot` dict, the full `ValuationModel` dict, and the requested
   `output_path` so a formula-driven 3-tab `.xlsx` workbook is written to disk.
6. **Write the Investment Committee Memo:** Synthesize all structured findings into a crisp,
   institutional-grade Markdown Investment Note containing:
   - **Executive Verdict:** Clear rating (`BUY`, `HOLD`, or `WATCH`) with 3-bullet thesis.
   - **Financial & Market Snapshot Table:** Revenue, EBITDA, EBITDA Margin, PAT, Net Debt, Net Debt/EBITDA,
     Market Cap, EV, Current EV/EBITDA, and Utilization (if disclosed).
   - **3-Case Valuation Summary (Bear / Base / Bull):** Target EV/EBITDA multiples, implied Equity Values,
     and valuation rationale.
   - **Business Model, TAM & 2025–2026 Sector Trends:** Grounded in both filing MD&A and cited live Tavily research.
   - **Competitive Advantages (Moats) & Top Risks / Mitigants.**
   - **Value-Creation Catalysts & Exit Angles.**
   - **Excel Model Artifact Confirmation:** State the saved `.xlsx` path and confirm its 3 formula-driven tabs.

Important operational rules:
- Never fabricate financial figures; always ground numbers in tool outputs.
- Always pass the complete, unmodified `FinancialSnapshot` and `ValuationModel` dictionaries to
  `build_excel_model`.
- If a tool returns an error, report it transparently and recover gracefully where possible.
"""


def build_orchestrator_agent(session_id: str | None = None) -> LlmAgent:
    """Constructs the complete FinSight ADK Hub-and-Spoke orchestrator tree."""
    extractor_agent = build_financial_extractor_agent(session_id=session_id)
    quant_agent = build_quant_valuation_agent(session_id=session_id)
    qual_team = build_qualitative_diligence_team(session_id=session_id)

    return LlmAgent(
        name="InvestmentCommitteeLead",
        model=build_k2_model(session_id=session_id, reasoning_effort="high"),
        description=(
            "Root Investment Committee orchestrator that coordinates PDF parsing, live market "
            "multiples, structured extraction, quantitative valuation, Tavily qualitative diligence, "
            "formula-driven Excel model generation, and final Investment Memo synthesis."
        ),
        instruction=_ORCHESTRATOR_INSTRUCTION,
        tools=[
            FunctionTool(parse_financial_pdf),
            FunctionTool(fetch_market_multiples),
            AgentTool(agent=extractor_agent),
            AgentTool(agent=quant_agent),
            AgentTool(agent=qual_team),
            FunctionTool(build_excel_model),
        ],
    )
