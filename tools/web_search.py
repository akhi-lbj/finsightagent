"""Tavily finance web search wrapped as a Google ADK LangchainTool."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from google.adk.integrations.langchain import LangchainTool
from langchain_core.tools import BaseTool as LangchainBaseTool
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field

load_dotenv()


class _TavilyQueryInput(BaseModel):
    query: str = Field(
        description=(
            "Targeted financial web search query for sector TAM/SAM, peer multiples, "
            "2025-2026 macro/regulatory shifts, or M&A/IPO exit precedents."
        )
    )


def _compact_tavily_result(raw: Any, fallback_topic: str | None = None) -> dict[str, Any]:
    """Trims verbose Tavily raw_content/snippets so tool outputs stay crisp and within token limits."""
    if not isinstance(raw, dict):
        return {"status": "success", "results": str(raw)[:2000]}
    compact_results = []
    for item in (raw.get("results") or [])[:4]:
        if isinstance(item, dict):
            compact_results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": str(item.get("content") or "")[:600],
                    "published_date": item.get("published_date"),
                }
            )
    out: dict[str, Any] = {
        "status": "success",
        "query": raw.get("query", ""),
        "results": compact_results,
    }
    if fallback_topic:
        out["fallback_topic"] = fallback_topic
    return out


class ResilientTavilyFinanceTool(LangchainBaseTool):
    """LangChain BaseTool wrapping `langchain_tavily.TavilySearch` safely for ADK.

    1. Queries `topic="finance", search_depth="advanced", max_results=5` first.
    2. If Tavily's strict `finance` index returns 0 hits (which raises `ToolException`),
       automatically falls back to `topic="general", search_depth="advanced"` so
       `SectorWebResearcher` never crashes mid-pipeline.
    3. Compacts results to keep context crisp and avoid `Maximum tokens reached` on K2 Horizon.
    """

    name: str = "tavily_search"
    description: str = (
        "Searches live financial news, sector TAM/SAM reports, peer valuation multiples, "
        "2025-2026 regulatory/macro shifts, and M&A/IPO exit precedents via Tavily."
    )
    args_schema: type[BaseModel] = _TavilyQueryInput

    def _run(self, query: str) -> Any:
        load_dotenv(override=False)
        api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
        if not api_key:
            return {
                "status": "error",
                "error": (
                    "TAVILY_API_KEY is missing in .env. Please add TAVILY_API_KEY=... to "
                    "c:\\Akhil\\AI_Engineer\\3rdProject\\.env and retry."
                ),
            }

        try:
            finance_tool = TavilySearch(
                max_results=5,
                topic="finance",
                search_depth="advanced",
                tavily_api_key=api_key,
            )
            return _compact_tavily_result(finance_tool.invoke({"query": query}))
        except Exception as finance_exc:
            # Fallback to general topic when finance-only index has no hits
            try:
                general_tool = TavilySearch(
                    max_results=5,
                    topic="general",
                    search_depth="advanced",
                    tavily_api_key=api_key,
                )
                return _compact_tavily_result(
                    general_tool.invoke({"query": query}),
                    fallback_topic="general",
                )
            except Exception as general_exc:
                return {
                    "status": "no_results",
                    "query": query,
                    "error": f"Finance search failed ({finance_exc}); general fallback failed ({general_exc}).",
                    "results": [],
                }


def build_tavily_search_tool() -> LangchainTool:
    """Creates a Google ADK LangchainTool wrapping ResilientTavilyFinanceTool."""
    return LangchainTool(
        tool=ResilientTavilyFinanceTool(),
        name="tavily_search",
        description=(
            "Searches live financial news, sector TAM/SAM reports, peer valuation multiples, "
            "2025-2026 regulatory/macro shifts, and M&A/IPO exit precedents via Tavily."
        ),
    )
