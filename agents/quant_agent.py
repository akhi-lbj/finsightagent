"""Agent 3: QuantValuationAgent (strict Pydantic input_schema + output_schema, zero tools)."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from llm_client import build_k2_model
from schemas import FinancialSnapshot, ValuationModel

_QUANT_INSTRUCTION = """You are a senior quantitative equity valuation modeler on an Investment Committee.

You receive a validated `FinancialSnapshot` JSON object and must output a strictly valid
`ValuationModel` JSON object.

Compute every quantitative metric accurately:
1. `revenue_yoy_growth_pct`: ((revenue_current - revenue_prior) / revenue_prior) * 100 (0.0 if prior is 0).
2. `ebitda_margin_pct`: (ebitda_current / revenue_current) * 100 (0.0 if revenue is 0).
3. `net_debt`: total_debt - cash_and_equivalents (negative means net cash).
4. `net_debt_to_ebitda`: net_debt / ebitda_current (0.0 if ebitda_current <= 0).
5. `debt_to_equity`: total_debt / total_equity (0.0 if total_equity <= 0).
6. `current_ev_to_ebitda`: current_enterprise_value / ebitda_current (0.0 if ebitda_current <= 0).
7. 3-Case EV/EBITDA Scenario Valuation:
   - Choose realistic institutional target EV/EBITDA multiples for `bear_target_ev_ebitda`,
     `base_target_ev_ebitda`, and `bull_target_ev_ebitda` anchored to the company's current
     EV/EBITDA, sector cyclicality, growth rate, EBITDA margin, utilization, and leverage profile.
   - Ensure `bear_target_ev_ebitda < base_target_ev_ebitda < bull_target_ev_ebitda`.
   - For each case compute:
     `implied_equity_value = (ebitda_current * target_ev_ebitda) - net_debt`
     (in the exact same currency/scale as `ebitda_current` and `net_debt`).
8. `valuation_rationale`: Provide a clear, concise institutional explanation of the Bear/Base/Bull
   multiple spread (e.g., discounting for cyclical freight/commodity exposure or leverage vs.
   awarding a premium for high utilization, net-cash balance sheet, or margin expansion).

Round all percentages, multiples, and currency values cleanly to 2 decimal places.
"""


def build_quant_valuation_agent(session_id: str | None = None) -> LlmAgent:
    """Builds the zero-tool QuantValuationAgent with FinancialSnapshot -> ValuationModel."""
    return LlmAgent(
        name="QuantValuationAgent",
        model=build_k2_model(session_id=session_id, reasoning_effort="high"),
        description=(
            "Computes operating/leverage ratios and Bear/Base/Bull EV/EBITDA scenario valuations "
            "from a validated FinancialSnapshot JSON object."
        ),
        instruction=_QUANT_INSTRUCTION,
        input_schema=FinancialSnapshot,
        output_schema=ValuationModel,
        output_key="valuation_model",
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
