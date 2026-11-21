"""Live market valuation multiples fetcher using yfinance."""

from __future__ import annotations

from typing import Any

import yfinance as yf


def fetch_market_multiples(ticker: str) -> dict[str, Any]:
    """Fetches live share price, valuation multiples, and 52-week range from Yahoo Finance.

    Args:
        ticker: Stock exchange ticker symbol (e.g., GESHIP.NS, SCI.NS, MAERSK-B.CO, AAPL).

    Returns:
        Dictionary with status, company metadata, share price, market cap, enterprise value,
        trailing P/E, EV/EBITDA, P/B, and 52-week high/low.
    """
    try:
        symbol = ticker.strip()
        if not symbol:
            return {"status": "error", "error": "Ticker symbol cannot be empty."}

        tk = yf.Ticker(symbol)
        info = tk.info or {}

        if not info or (
            info.get("marketCap") is None
            and info.get("currentPrice") is None
            and info.get("regularMarketPrice") is None
        ):
            return {
                "status": "error",
                "ticker": symbol,
                "error": f"No live market data returned from Yahoo Finance for ticker '{symbol}'.",
            }

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        currency = info.get("currency") or "USD"
        market_cap = info.get("marketCap")
        enterprise_value = info.get("enterpriseValue")

        return {
            "status": "success",
            "ticker": symbol,
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "currency": currency,
            "current_price": current_price,
            "marketCap": market_cap,
            "enterpriseValue": enterprise_value,
            "trailingPE": info.get("trailingPE"),
            "forwardPE": info.get("forwardPE"),
            "enterpriseToEbitda": info.get("enterpriseToEbitda"),
            "priceToBook": info.get("priceToBook"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "totalDebt": info.get("totalDebt"),
            "totalCash": info.get("totalCash"),
            "ebitda": info.get("ebitda"),
            "totalRevenue": info.get("totalRevenue"),
            "note": (
                "marketCap, enterpriseValue, totalDebt, totalCash, ebitda, and totalRevenue "
                "are in raw base units of `currency` (not scaled to Millions or Crores)."
            ),
        }
    except Exception as exc:
        return {"status": "error", "ticker": ticker, "error": f"yfinance lookup failed: {exc}"}
