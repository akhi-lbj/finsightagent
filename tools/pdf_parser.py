"""PDF financial table and MD&A extractor using pdfplumber."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import pdfplumber

# Keywords used to prioritize pages containing financial statements, KPIs, and MD&A/risks.
_FINANCIAL_KEYWORDS = (
    "revenue",
    "income statement",
    "statement of profit",
    "profit and loss",
    "ebitda",
    "balance sheet",
    "cash flow",
    "borrowings",
    "total debt",
    "shareholders' equity",
    "total equity",
    "capital expenditure",
    "capex",
    "management discussion",
    "md&a",
    "outlook",
    "utilization",
    "fleet",
    "risk factors",
    "segment",
    "consolidated",
    "financial results",
)

_MAX_OUTPUT_CHARS = 48_000


def _table_to_markdown(table: list[list[str | None]]) -> str:
    """Converts a pdfplumber 2D table into a clean GitHub-flavored Markdown table."""
    cleaned_rows: list[list[str]] = []
    for row in table:
        if not row:
            continue
        cells = [re.sub(r"\s+", " ", (cell or "")).strip().replace("|", "\\|") for cell in row]
        if any(cells):
            cleaned_rows.append(cells)

    if len(cleaned_rows) < 2:
        return ""

    col_count = max(len(r) for r in cleaned_rows)
    normalized = [r + [""] * (col_count - len(r)) for r in cleaned_rows]

    header = "| " + " | ".join(normalized[0]) + " |"
    separator = "| " + " | ".join(["---"] * col_count) + " |"
    body = ["| " + " | ".join(r) + " |" for r in normalized[1:]]
    return "\n".join([header, separator, *body])


def _score_page(text: str, table_count: int) -> int:
    """Scores a page for financial statement / MD&A relevance."""
    lower = text.lower()
    score = table_count * 4
    for kw in _FINANCIAL_KEYWORDS:
        if kw in lower:
            score += 2
    # Bonus for dense numeric content (tables/financial figures)
    digits = sum(ch.isdigit() for ch in text)
    if digits > 150:
        score += 3
    return score


def parse_financial_pdf(file_path: str) -> dict[str, Any]:
    """Extracts financial tables (as Markdown) and MD&A narrative text from a PDF filing.

    Filters and ranks pages for financial statements, balance sheet, cash flows,
    utilization KPIs, and management commentary so the output fits cleanly within
    the LLM context window.

    Args:
        file_path: Absolute or relative path to the quarterly/annual PDF filing on disk.

    Returns:
        Dictionary containing status, metadata, extracted_markdown_tables, and mda_text.
    """
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            return {"status": "error", "error": f"PDF file not found: {file_path}"}

        page_records: list[dict[str, Any]] = []
        with pdfplumber.open(str(path)) as pdf:
            total_pages = len(pdf.pages)
            for idx, page in enumerate(pdf.pages, start=1):
                raw_text = (page.extract_text() or "").strip()
                raw_tables = page.extract_tables() or []
                md_tables = [md for tbl in raw_tables if (md := _table_to_markdown(tbl))]
                score = _score_page(raw_text, len(md_tables))
                page_records.append(
                    {
                        "page_number": idx,
                        "score": score,
                        "text": raw_text,
                        "tables": md_tables,
                    }
                )

        # Keep first 2 pages (cover/highlights) + highest-scoring financial/MD&A pages
        must_keep = {1, 2}
        ranked = sorted(page_records, key=lambda r: (-r["score"], r["page_number"]))
        selected_nums = set(must_keep)
        for rec in ranked:
            if len(selected_nums) >= 18:
                break
            if rec["score"] > 0 or len(selected_nums) < 8:
                selected_nums.add(rec["page_number"])

        selected_pages = [r for r in page_records if r["page_number"] in selected_nums]
        selected_pages.sort(key=lambda r: r["page_number"])

        table_sections: list[str] = []
        text_sections: list[str] = []
        char_budget = _MAX_OUTPUT_CHARS

        for rec in selected_pages:
            pg = rec["page_number"]
            if rec["tables"]:
                block = f"### Page {pg} Tables\n" + "\n\n".join(rec["tables"])
                if len(block) <= char_budget:
                    table_sections.append(block)
                    char_budget -= len(block)

            if rec["text"]:
                snippet = rec["text"][:4000]
                tblock = f"### Page {pg} Text\n{snippet}"
                if len(tblock) <= char_budget:
                    text_sections.append(tblock)
                    char_budget -= len(tblock)

        return {
            "status": "success",
            "file_name": os.path.basename(str(path)),
            "total_pages": total_pages,
            "pages_extracted": [r["page_number"] for r in selected_pages],
            "extracted_markdown_tables": "\n\n".join(table_sections) or "No structured tables detected.",
            "mda_text": "\n\n".join(text_sections) or "No narrative text extracted.",
        }
    except Exception as exc:
        return {"status": "error", "error": f"Failed to parse PDF '{file_path}': {exc}"}
