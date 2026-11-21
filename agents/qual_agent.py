"""Agent 4: QualitativeDiligenceTeam (2-step SequentialAgent wrapped as AgentTool).

Sub-Agent 4A: SectorWebResearcher (LlmAgent with LangchainTool(TavilySearch)) -> session.state["live_market_research"]
Sub-Agent 4B: QualitativeRiskSynthesizer (LlmAgent with output_schema=QualitativeDiligence, zero tools)
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext

from llm_client import build_k2_model
from schemas import QualitativeDiligence
from tools.web_search import build_tavily_search_tool


async def _ensure_research_state(callback_context: CallbackContext) -> None:
    """Ensures `live_market_research` exists in session state before synthesis."""
    if not callback_context.state.get("live_market_research"):
        callback_context.state["live_market_research"] = (
            "No live web research text was saved by SectorWebResearcher; rely on the "
            "conversation history, tool responses above, and the filing's management commentary."
        )


_RESEARCHER_INSTRUCTION = """You are a sector and competitive intelligence equity researcher.

Using the company name, ticker, sector, and management commentary context provided in the request,
execute 2 to 3 targeted live financial web searches using the `tavily_search` tool to gather:
1. Total Addressable Market (TAM/SAM), industry growth outlook, and 2025-2026 macro/regulatory shifts.
2. Key peers, competitive positioning, and sector valuation / operational benchmarks.
3. Recent 2025-2026 M&A transactions, IPOs, asset sales, or strategic value-creation catalysts in the sector.

CRITICAL: After calling `tavily_search`, you MUST write a final non-empty Markdown research brief
synthesizing your live web findings (including source names/URLs and dates wherever returned by
Tavily). Do not output JSON—write a structured Markdown research brief so it is saved into
`session.state["live_market_research"]` for the downstream synthesizer.
"""

_SYNTHESIZER_INSTRUCTION = """You are a senior investment diligence synthesizer.

You have access to:
1. The company and filing context from the user request (including management commentary).
2. Live web market intelligence gathered by the SectorWebResearcher:
{live_market_research?}

Synthesize both the filing's management commentary and the live market research into a strictly
valid `QualitativeDiligence` JSON object:
- `business_model_summary`: Unit economics, revenue drivers, and operating leverage.
- `tam_and_sector_trends`: TAM/SAM sizing and cited 2025-2026 macro, regulatory, and demand shifts.
- `competitive_advantages`: Up to 4 sharp, non-generic economic moats (max 4 list items).
- `key_risks_and_mitigants`: Up to 5 concrete downside risks paired with mitigants (max 5 list items,
  formatted as `"Risk: ... | Mitigant: ..."`).
- `exit_and_value_creation_angles`: Re-rating catalysts, capital allocation levers, and M&A/IPO precedents.
"""


def build_qualitative_diligence_team(session_id: str | None = None) -> SequentialAgent:
    """Builds the 2-step SequentialAgent (Tavily Web Researcher -> Schema Synthesizer)."""
    tavily_tool = build_tavily_search_tool()

    sector_web_researcher = LlmAgent(
        name="SectorWebResearcher",
        model=build_k2_model(session_id=session_id, reasoning_effort="medium"),
        description="Runs live Tavily finance web searches for TAM, peers, macro shifts, and M&A precedents.",
        instruction=_RESEARCHER_INSTRUCTION,
        tools=[tavily_tool],
        output_key="live_market_research",
    )

    qualitative_risk_synthesizer = LlmAgent(
        name="QualitativeRiskSynthesizer",
        model=build_k2_model(session_id=session_id, reasoning_effort="high"),
        description="Synthesizes filing commentary and live web research into a QualitativeDiligence JSON object.",
        instruction=_SYNTHESIZER_INSTRUCTION,
        output_schema=QualitativeDiligence,
        output_key="qualitative_diligence",
        before_agent_callback=_ensure_research_state,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    return SequentialAgent(
        name="QualitativeDiligenceTeam",
        description=(
            "Performs live Tavily financial web research on sector TAM, peers, 2025-2026 macro/regulatory "
            "trends, and exit precedents, then returns a strictly validated QualitativeDiligence JSON object."
        ),
        sub_agents=[sector_web_researcher, qualitative_risk_synthesizer],
    )
