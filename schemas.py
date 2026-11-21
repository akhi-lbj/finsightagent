"""Pydantic data contracts for FinSight ADK.

All schemas are intentionally flat (single-level) with descriptive field names
for optimal IFM K2 Horizon structured JSON decoding.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FinancialSnapshot(BaseModel):
    """Normalized financial metrics extracted from a company filing and live market data."""

    company_name: str = Field(description="Full legal or common name of the company.")
    ticker: str = Field(description="Exchange ticker symbol (e.g., GESHIP.NS, SCI.NS, MAERSK-B.CO).")
    reporting_period: str = Field(description="Fiscal period covered by the filing (e.g., Q3 FY26, FY2025).")
    currency: str = Field(description="Standardized reporting currency and scale (e.g., INR Crores, USD Millions).")
    revenue_current: float = Field(description="Current period total revenue in the standardized currency/scale.")
    revenue_prior: float = Field(description="Prior comparable period total revenue in the same currency/scale.")
    ebitda_current: float = Field(description="Current period EBITDA in the standardized currency/scale.")
    ebitda_prior: float = Field(description="Prior comparable period EBITDA in the same currency/scale.")
    net_income_current: float = Field(description="Current period net income / PAT in the standardized currency/scale.")
    total_debt: float = Field(description="Total short-term plus long-term debt on the balance sheet.")
    cash_and_equivalents: float = Field(description="Cash, cash equivalents, and marketable securities.")
    total_equity: float = Field(description="Total shareholders' equity / net worth.")
    capex: float = Field(description="Capital expenditures for the reporting period (positive number).")
    current_enterprise_value: float = Field(description="Current Enterprise Value in the same currency/scale as revenue.")
    current_market_cap: float = Field(description="Current Market Capitalization in the same currency/scale as revenue.")
    asset_or_fleet_utilization_pct: float | None = Field(
        default=None,
        description="Asset, plant, or fleet utilization percentage (0-100) if disclosed, otherwise null.",
    )
    management_commentary_summary: str = Field(
        description="Concise summary of key MD&A takeaways, operational drivers, and outlook from the filing."
    )


class ValuationModel(BaseModel):
    """Quantitative operating ratios, leverage metrics, and 3-case EV/EBITDA scenario valuation."""

    revenue_yoy_growth_pct: float = Field(description="Year-over-year revenue growth percentage.")
    ebitda_margin_pct: float = Field(description="Current EBITDA margin as a percentage of current revenue.")
    net_debt: float = Field(description="Total debt minus cash and equivalents (can be negative if net cash).")
    net_debt_to_ebitda: float = Field(description="Net Debt divided by Current EBITDA.")
    debt_to_equity: float = Field(description="Total Debt divided by Total Equity.")
    current_ev_to_ebitda: float = Field(description="Current Enterprise Value divided by Current EBITDA.")
    bear_target_ev_ebitda: float = Field(description="Bear case target EV/EBITDA multiple.")
    bear_implied_equity_value: float = Field(
        description="Bear case implied Equity Value = (EBITDA * Bear Multiple) - Net Debt."
    )
    base_target_ev_ebitda: float = Field(description="Base case target EV/EBITDA multiple.")
    base_implied_equity_value: float = Field(
        description="Base case implied Equity Value = (EBITDA * Base Multiple) - Net Debt."
    )
    bull_target_ev_ebitda: float = Field(description="Bull case target EV/EBITDA multiple.")
    bull_implied_equity_value: float = Field(
        description="Bull case implied Equity Value = (EBITDA * Bull Multiple) - Net Debt."
    )
    valuation_rationale: str = Field(
        description="Institutional rationale explaining the Bear/Base/Bull multiple spread and key drivers."
    )


class QualitativeDiligence(BaseModel):
    """Sector intelligence, competitive moat analysis, downside risks, and exit angles."""

    business_model_summary: str = Field(
        description="Unit economics, revenue streams, and operating leverage of the business."
    )
    tam_and_sector_trends: str = Field(
        description="Total Addressable Market (TAM/SAM), 2025-2026 macro/regulatory shifts, and cited sector trends."
    )
    competitive_advantages: list[str] = Field(
        description="Up to 4 distinct economic moats or structural competitive advantages."
    )
    key_risks_and_mitigants: list[str] = Field(
        description="Up to 5 key downside risks paired with concrete mitigants."
    )
    exit_and_value_creation_angles: str = Field(
        description="Value-creation levers, re-rating catalysts, and M&A/IPO exit precedents."
    )
