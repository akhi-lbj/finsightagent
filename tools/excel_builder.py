"""Formula-driven 3-tab Excel financial model builder using openpyxl."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_HEADER_FILL = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
_SUBHEADER_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
_ACCENT_FILL = PatternFill(start_color="F2F6FC", end_color="F2F6FC", fill_type="solid")
_HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
_TITLE_FONT = Font(name="Calibri", size=14, bold=True, color="1B365D")
_BOLD_FONT = Font(name="Calibri", size=11, bold=True, color="000000")
_REGULAR_FONT = Font(name="Calibri", size=11, color="000000")
_THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)

_NUM_FMT = "#,##0.00"
_PCT_FMT = "0.0%"
_MULT_FMT = '0.00"x"'


def _style_header_row(ws: Any, row_idx: int, col_count: int) -> None:
    for col in range(1, col_count + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _THIN_BORDER


def _autofit_columns(ws: Any, min_width: int = 16, max_width: int = 44) -> None:
    for col_cells in ws.columns:
        col_letter = get_column_letter(col_cells[0].column)
        longest = max((len(str(c.value or "")) for c in col_cells), default=0)
        ws.column_dimensions[col_letter].width = max(min_width, min(longest + 4, max_width))


def build_excel_model(
    snapshot: dict[str, Any],
    valuation: dict[str, Any],
    output_path: str = "",
) -> dict[str, Any]:
    """Generates a 3-tab formula-driven institutional Excel financial model (.xlsx).

    Tabs created:
      1. `1_Financial_Summary`: Normalized historical/current P&L, balance sheet, and market inputs.
      2. `2_Ratios_&_Multiples`: Live Excel formulas referencing Tab 1 (`=(B4-C4)/C4`, `=B5/B4`, etc.).
      3. `3_Scenario_Analysis`: Bear, Base, and Bull EV/EBITDA implied valuation formulas.

    Args:
        snapshot: FinancialSnapshot dictionary (company_name, ticker, revenue_current, etc.).
        valuation: ValuationModel dictionary (bear/base/bull target EV/EBITDA multiples, rationale).
        output_path: Destination file path for the generated `.xlsx` workbook. If empty, saves
            into `./outputs/<ticker>_FinSight_Model.xlsx`.

    Returns:
        Dictionary with status, output_path, and sheet_names.
    """
    try:
        ticker_raw = str(snapshot.get("ticker") or "FinSight")
        safe_ticker = "".join(c if c.isalnum() or c in "-_" else "_" for c in ticker_raw)
        if not output_path or not output_path.strip():
            dest = (Path.cwd() / "outputs" / f"{safe_ticker}_FinSight_Model.xlsx").resolve()
        else:
            dest = Path(output_path).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        company = str(snapshot.get("company_name") or "Target Company")
        ticker = str(snapshot.get("ticker") or "N/A")
        period = str(snapshot.get("reporting_period") or "Current Period")
        currency = str(snapshot.get("currency") or "USD Millions")

        def _f(d: dict[str, Any], key: str, default: float = 0.0) -> float:
            val = d.get(key)
            if val is None:
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        wb = Workbook()

        # ------------------------------------------------------------------
        # TAB 1: 1_Financial_Summary
        # Row layout is fixed so formulas on Tabs 2 and 3 are deterministic:
        #   Row 4: Revenue (B4 = Current, C4 = Prior, D4 = =(B4-C4)/C4)
        #   Row 5: EBITDA  (B5 = Current, C5 = Prior, D5 = =(B5-C5)/C5)
        #   Row 6: Net Income (B6 = Current)
        #   Row 7: Total Debt (B7 = Current)
        #   Row 8: Cash & Equivalents (B8 = Current)
        #   Row 9: Net Debt (=B7-B8)
        #   Row 10: Total Equity (B10 = Current)
        #   Row 11: CapEx (B11 = Current)
        #   Row 12: Enterprise Value (B12 = Current)
        #   Row 13: Market Cap (B13 = Current)
        #   Row 14: Asset / Fleet Utilization % (B14)
        # ------------------------------------------------------------------
        ws1 = wb.active
        ws1.title = "1_Financial_Summary"
        ws1["A1"] = f"FinSight ADK — Financial Summary: {company} ({ticker})"
        ws1["A1"].font = _TITLE_FONT
        ws1["A2"] = f"Reporting Period: {period}  |  Units: {currency}"
        ws1["A2"].font = Font(name="Calibri", size=10, italic=True, color="595959")

        ws1.append(["Line Item", "Current Period", "Prior Period", "YoY Change / Notes"])
        _style_header_row(ws1, 3, 4)

        summary_rows = [
            ("Revenue", _f(snapshot, "revenue_current"), _f(snapshot, "revenue_prior"), "=IF(C4<>0,(B4-C4)/C4,0)", _NUM_FMT, _PCT_FMT),
            ("EBITDA", _f(snapshot, "ebitda_current"), _f(snapshot, "ebitda_prior"), "=IF(C5<>0,(B5-C5)/C5,0)", _NUM_FMT, _PCT_FMT),
            ("Net Income (PAT)", _f(snapshot, "net_income_current"), None, "=IF(B4<>0,B6/B4,0)", _NUM_FMT, _PCT_FMT),
            ("Total Debt", _f(snapshot, "total_debt"), None, "Balance Sheet", _NUM_FMT, None),
            ("Cash & Equivalents", _f(snapshot, "cash_and_equivalents"), None, "Balance Sheet", _NUM_FMT, None),
            ("Net Debt", "=B7-B8", None, "Formula: Total Debt - Cash", _NUM_FMT, None),
            ("Total Equity", _f(snapshot, "total_equity"), None, "Balance Sheet", _NUM_FMT, None),
            ("Capital Expenditure (CapEx)", _f(snapshot, "capex"), None, "Cash Flow Statement", _NUM_FMT, None),
            ("Current Enterprise Value", _f(snapshot, "current_enterprise_value"), None, "Live Market Data", _NUM_FMT, None),
            ("Current Market Cap", _f(snapshot, "current_market_cap"), None, "Live Market Data", _NUM_FMT, None),
            (
                "Asset / Fleet Utilization (%)",
                (_f(snapshot, "asset_or_fleet_utilization_pct") / 100.0)
                if snapshot.get("asset_or_fleet_utilization_pct") is not None
                else None,
                None,
                "Operational KPI",
                _PCT_FMT,
                None,
            ),
        ]

        for r_idx, (label, cur_val, prior_val, note_or_formula, val_fmt, d_fmt) in enumerate(summary_rows, start=4):
            ws1.cell(row=r_idx, column=1, value=label).font = _BOLD_FONT if label in {"Revenue", "EBITDA", "Net Debt"} else _REGULAR_FONT
            c_cur = ws1.cell(row=r_idx, column=2, value=cur_val)
            c_cur.font = _BOLD_FONT if label == "Net Debt" else _REGULAR_FONT
            if cur_val is not None:
                c_cur.number_format = val_fmt

            c_prior = ws1.cell(row=r_idx, column=3, value=prior_val)
            c_prior.font = _REGULAR_FONT
            if prior_val is not None:
                c_prior.number_format = val_fmt

            c_note = ws1.cell(row=r_idx, column=4, value=note_or_formula)
            c_note.font = _REGULAR_FONT
            if d_fmt:
                c_note.number_format = d_fmt

            for col in range(1, 5):
                cell = ws1.cell(row=r_idx, column=col)
                cell.border = _THIN_BORDER
                if r_idx % 2 == 0:
                    cell.fill = _ACCENT_FILL

        _autofit_columns(ws1)

        # ------------------------------------------------------------------
        # TAB 2: 2_Ratios_&_Multiples
        # Live formulas referencing '1_Financial_Summary'
        # ------------------------------------------------------------------
        ws2 = wb.create_sheet(title="2_Ratios_&_Multiples")
        ws2["A1"] = f"Operating Ratios, Leverage & Valuation Multiples — {company} ({ticker})"
        ws2["A1"].font = _TITLE_FONT
        ws2["A2"] = "All metrics dynamically linked via Excel formulas to 1_Financial_Summary"
        ws2["A2"].font = Font(name="Calibri", size=10, italic=True, color="595959")

        ws2.append(["Metric", "Formula Value", "Category", "Formula Description"])
        _style_header_row(ws2, 3, 4)

        ratio_rows = [
            ("Revenue YoY Growth (%)", "=IF('1_Financial_Summary'!C4<>0,('1_Financial_Summary'!B4-'1_Financial_Summary'!C4)/'1_Financial_Summary'!C4,0)", "Growth", "(Current Rev - Prior Rev) / Prior Rev", _PCT_FMT),
            ("EBITDA YoY Growth (%)", "=IF('1_Financial_Summary'!C5<>0,('1_Financial_Summary'!B5-'1_Financial_Summary'!C5)/'1_Financial_Summary'!C5,0)", "Growth", "(Current EBITDA - Prior EBITDA) / Prior EBITDA", _PCT_FMT),
            ("EBITDA Margin (%)", "=IF('1_Financial_Summary'!B4<>0,'1_Financial_Summary'!B5/'1_Financial_Summary'!B4,0)", "Profitability", "Current EBITDA / Current Revenue", _PCT_FMT),
            ("Net Income Margin (%)", "=IF('1_Financial_Summary'!B4<>0,'1_Financial_Summary'!B6/'1_Financial_Summary'!B4,0)", "Profitability", "Current Net Income / Current Revenue", _PCT_FMT),
            ("Net Debt", "='1_Financial_Summary'!B7-'1_Financial_Summary'!B8", "Leverage", "Total Debt - Cash & Equivalents", _NUM_FMT),
            ("Net Debt / EBITDA", "=IF('1_Financial_Summary'!B5<>0,('1_Financial_Summary'!B7-'1_Financial_Summary'!B8)/'1_Financial_Summary'!B5,0)", "Leverage", "(Total Debt - Cash) / Current EBITDA", _MULT_FMT),
            ("Debt / Equity", "=IF('1_Financial_Summary'!B10<>0,'1_Financial_Summary'!B7/'1_Financial_Summary'!B10,0)", "Leverage", "Total Debt / Total Equity", _MULT_FMT),
            ("CapEx / Revenue (%)", "=IF('1_Financial_Summary'!B4<>0,'1_Financial_Summary'!B11/'1_Financial_Summary'!B4,0)", "Capital Intensity", "CapEx / Current Revenue", _PCT_FMT),
            ("Current EV / EBITDA", "=IF('1_Financial_Summary'!B5<>0,'1_Financial_Summary'!B12/'1_Financial_Summary'!B5,0)", "Valuation", "Enterprise Value / Current EBITDA", _MULT_FMT),
            ("Current EV / Revenue", "=IF('1_Financial_Summary'!B4<>0,'1_Financial_Summary'!B12/'1_Financial_Summary'!B4,0)", "Valuation", "Enterprise Value / Current Revenue", _MULT_FMT),
            ("Implied P/E (Market Cap / PAT)", "=IF('1_Financial_Summary'!B6<>0,'1_Financial_Summary'!B13/'1_Financial_Summary'!B6,0)", "Valuation", "Market Cap / Current Net Income", _MULT_FMT),
        ]

        for r_idx, (metric, formula, category, desc, fmt) in enumerate(ratio_rows, start=4):
            ws2.cell(row=r_idx, column=1, value=metric).font = _BOLD_FONT
            c_val = ws2.cell(row=r_idx, column=2, value=formula)
            c_val.font = _REGULAR_FONT
            c_val.number_format = fmt
            ws2.cell(row=r_idx, column=3, value=category).font = _REGULAR_FONT
            ws2.cell(row=r_idx, column=4, value=desc).font = _REGULAR_FONT

            for col in range(1, 5):
                cell = ws2.cell(row=r_idx, column=col)
                cell.border = _THIN_BORDER
                if r_idx % 2 == 0:
                    cell.fill = _ACCENT_FILL

        _autofit_columns(ws2)

        # ------------------------------------------------------------------
        # TAB 3: 3_Scenario_Analysis
        # Bear / Base / Bull EV/EBITDA implied valuation formulas
        # ------------------------------------------------------------------
        ws3 = wb.create_sheet(title="3_Scenario_Analysis")
        ws3["A1"] = f"3-Case EV/EBITDA Scenario Valuation — {company} ({ticker})"
        ws3["A1"].font = _TITLE_FONT
        ws3["A2"] = f"Units: {currency}  |  All Implied EV, Equity Value & Upside cells are live formulas"
        ws3["A2"].font = Font(name="Calibri", size=10, italic=True, color="595959")

        ws3.append([
            "Scenario",
            "Target EV/EBITDA",
            "Current EBITDA",
            "Implied Enterprise Value",
            "Less: Net Debt",
            "Implied Equity Value",
            "Implied Upside / (Downside) %",
        ])
        _style_header_row(ws3, 3, 7)

        scenarios = [
            ("Bear Case", _f(valuation, "bear_target_ev_ebitda", 6.0)),
            ("Base Case", _f(valuation, "base_target_ev_ebitda", 8.0)),
            ("Bull Case", _f(valuation, "bull_target_ev_ebitda", 10.0)),
        ]

        for r_idx, (case_name, target_mult) in enumerate(scenarios, start=4):
            ws3.cell(row=r_idx, column=1, value=case_name).font = _BOLD_FONT
            c_mult = ws3.cell(row=r_idx, column=2, value=target_mult)
            c_mult.number_format = _MULT_FMT
            c_ebitda = ws3.cell(row=r_idx, column=3, value="='1_Financial_Summary'!B5")
            c_ebitda.number_format = _NUM_FMT
            c_imp_ev = ws3.cell(row=r_idx, column=4, value=f"=B{r_idx}*C{r_idx}")
            c_imp_ev.number_format = _NUM_FMT
            c_nd = ws3.cell(row=r_idx, column=5, value="='1_Financial_Summary'!B9")
            c_nd.number_format = _NUM_FMT
            c_imp_eq = ws3.cell(row=r_idx, column=6, value=f"=D{r_idx}-E{r_idx}")
            c_imp_eq.font = _BOLD_FONT
            c_imp_eq.number_format = _NUM_FMT
            c_upside = ws3.cell(
                row=r_idx,
                column=7,
                value=f"=IF('1_Financial_Summary'!B13<>0,(F{r_idx}-'1_Financial_Summary'!B13)/'1_Financial_Summary'!B13,0)",
            )
            c_upside.font = _BOLD_FONT
            c_upside.number_format = _PCT_FMT

            for col in range(1, 8):
                cell = ws3.cell(row=r_idx, column=col)
                cell.border = _THIN_BORDER
                if case_name == "Base Case":
                    cell.fill = _SUBHEADER_FILL

        rationale = str(valuation.get("valuation_rationale") or "")
        if rationale:
            ws3["A8"] = "Valuation Rationale:"
            ws3["A8"].font = _BOLD_FONT
            ws3["A9"] = rationale
            ws3["A9"].alignment = Alignment(wrap_text=True, vertical="top")
            ws3.merge_cells("A9:G12")

        _autofit_columns(ws3)

        wb.save(str(dest))
        return {
            "status": "success",
            "output_path": str(dest),
            "sheet_names": wb.sheetnames,
        }
    except Exception as exc:
        return {"status": "error", "error": f"Failed to build Excel model: {exc}"}
