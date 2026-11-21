"""Agent 2: FinancialExtractorAgent (strict Pydantic JSON extraction, zero external tools)."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from llm_client import build_k2_model
from schemas import FinancialSnapshot

_EXTRACTOR_INSTRUCTION = """You are a strict institutional financial data parser and normalizer.

You will receive raw Markdown tables and MD&A text extracted from a company's quarterly or annual
PDF filing, alongside live market multiples from Yahoo Finance.

Your sole job is to normalize every financial figure into a single consistent currency and scale
(e.g., "INR Crores" or "USD Millions") and output a strictly valid `FinancialSnapshot` JSON object.

Normalization rules:
1. Pick the primary reporting currency and unit scale used in the PDF filing (e.g., INR Crores for
   Indian filings like GESHIP.NS / SCI.NS, or USD Millions for international filings like MAERSK-B.CO).
2. Convert Yahoo Finance's raw `marketCap` and `enterpriseValue` (which are in raw base units) into
   the EXACT same currency and unit scale as the PDF's revenue and EBITDA:
   - Example: INR raw -> INR Crores: divide by 10,000,000 (1e7).
   - Example: USD raw -> USD Millions: divide by 1,000,000 (1e6).
3. If EBITDA is not explicitly printed as a single line, compute it accurately from Operating Profit
   (EBIT) + Depreciation & Amortization, or use the disclosed Adjusted EBITDA.
4. Keep `capex` as a positive float representing cash outflows for capital expenditure.
5. Set `asset_or_fleet_utilization_pct` to a float between 0 and 100 if disclosed (e.g., fleet
   utilization, load factor, plant capacity utilization), otherwise `null`.
6. Write a crisp, factual `management_commentary_summary` capturing revenue/margin drivers,
   freight/pricing trends, capex plans, and guidance from MD&A.
7. Never invent missing numbers; if a minor line item is absent from the filing, fall back to the
   Yahoo Finance value (properly scaled) or 0.0 if truly unavailable.
"""


def build_financial_extractor_agent(session_id: str | None = None) -> LlmAgent:
    """Builds the zero-tool FinancialExtractorAgent with output_schema=FinancialSnapshot."""
    return LlmAgent(
        name="FinancialExtractorAgent",
        model=build_k2_model(session_id=session_id, reasoning_effort="medium"),
        description=(
            "Parses raw PDF financial tables, MD&A text, and live Yahoo Finance market data "
            "into a strictly normalized FinancialSnapshot JSON object."
        ),
        instruction=_EXTRACTOR_INSTRUCTION,
        output_schema=FinancialSnapshot,
        output_key="financial_snapshot",
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
