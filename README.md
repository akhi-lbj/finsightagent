# 📊 FinSight ADK

**FinSight ADK** is an AI-powered equity research workbench that turns a company's quarterly/annual PDF filing and a stock ticker into:
1. A **3-tab, formula-driven Excel financial model** (`.xlsx`)
2. An **institutional Investment Committee Memo** (`BUY` / `HOLD` / `WATCH`) backed by live market multiples and live web research.

It is built with **Google ADK** (`LlmAgent`, `SequentialAgent`, `AgentTool`, `FunctionTool`, `LangchainTool`), **IFM K2 Horizon** (`IFM/K2-Horizon-375B-A23B`), **Tavily Finance Search**, **Yahoo Finance (`yfinance`)**, **pdfplumber**, and **openpyxl** — and runs in both **`adk web`** and **Streamlit**.

---

## 🧠 How the Architecture Works (Simple Overview)

Think of **FinSight ADK** like a real investment committee team: **one lead analyst** coordinates **three specialists** and **three deterministic tools** in sequence.

```text
                        ┌──────────────────────────────────────┐
                        │        User (adk web / Streamlit)     │
                        │   Ticker (e.g. GESHIP.NS) + PDF File │
                        └──────────────────┬───────────────────┘
                                           │
                                           ▼
                        ┌──────────────────────────────────────┐
                        │       InvestmentCommitteeLead        │
                        │        (Root Orchestrator Agent)     │
                        └─┬──────┬──────────┬──────────┬─────┬─┘
                          │      │          │          │     │
         1. Read PDF ─────┘      │          │          │     └───── 5. Build Excel
            │                    │          │          │                │
            ▼                    ▼          │          │                ▼
   ┌─────────────────┐  ┌─────────────────┐ │          │      ┌───────────────────┐
   │parse_financial_ │  │ fetch_market_   │ │          │      │ build_excel_model │
   │      pdf        │  │   multiples     │ │          │      │  (3-Tab .xlsx w/  │
   │  (pdfplumber)   │  │   (yfinance)    │ │          │      │   live formulas)  │
   └─────────────────┘  └─────────────────┘ │          │      └───────────────────┘
                          ▲                 │          │
                   2. Live Multiples        │          │
                                            │          │
                 ┌──────────────────────────┘          └──────────────────────────┐
                 │ 3. Clean & Normalize                                           │ 4. Model & Diligence
                 ▼                                                                ▼
   ┌───────────────────────────┐                            ┌──────────────────────────────────────────┐
   │  FinancialExtractorAgent  │                            │           Two Parallel Analyses          │
   │   (PDF + Market -> JSON)  │                            ├────────────────────┬─────────────────────┤
   │  Output: FinancialSnapshot│                            │QuantValuationAgent │QualitativeDiligence │
   └───────────────────────────┘                            │(Ratios + Bear/Base │Team (Sequential):   │
                                                            │ /Bull EV/EBITDA)   │ 4A. SectorWeb       │
                                                            │Output:             │     Researcher      │
                                                            │ ValuationModel     │     (Tavily Search) │
                                                            │                    │ 4B. QualitativeRisk │
                                                            │                    │     Synthesizer   │
                                                            │                    │Output:              │
                                                            │                    │ QualitativeDiligence│
                                                            └────────────────────┴─────────────────────┘
```

### Step-by-Step Flow
1. **Read the Filing (`parse_financial_pdf`)**: Extracts financial tables as clean Markdown and pulls key MD&A / outlook pages from the uploaded PDF.
2. **Fetch Live Market Data (`fetch_market_multiples`)**: Pulls live share price, Market Cap, Enterprise Value, P/E, EV/EBITDA, P/B, and 52-week range from Yahoo Finance.
3. **Normalize Numbers (`FinancialExtractorAgent`)**: Converts messy filing tables + raw market numbers into one consistent currency/scale (`FinancialSnapshot` JSON).
4. **Analyze Valuation & Sector (`QuantValuationAgent` + `QualitativeDiligenceTeam`)**:
   - **QuantValuationAgent** computes YoY growth, EBITDA margin, Net Debt, Net Debt/EBITDA, Debt/Equity, and **Bear / Base / Bull** EV/EBITDA scenarios (`ValuationModel` JSON).
   - **QualitativeDiligenceTeam** runs a 2-step `SequentialAgent`: first **SectorWebResearcher** searches live finance news via Tavily for TAM, peer positioning, and 2026+ regulatory/macro shifts; then **QualitativeRiskSynthesizer** combines that with management commentary (`QualitativeDiligence` JSON).
5. **Generate Excel Workbook (`build_excel_model`)**: Writes a 3-tab `.xlsx` workbook (`1_Financial_Summary`, `2_Ratios_&_Multiples`, `3_Scenario_Analysis`) using **real Excel formulas** (`=(B4-C4)/C4`, `=B7-B8`, `=D4-E4`).
6. **Deliver Investment Memo**: `InvestmentCommitteeLead` synthesizes everything into a structured `BUY` / `HOLD` / `WATCH` Investment Committee Memo.

### Why Specialists Are Separated (`AgentTool` + `output_schema`)
- Agents that enforce strict JSON output (`output_schema=...`) have **zero external tools** attached so the LLM never gets stuck in tool-calling loops.
- `QualitativeDiligenceTeam` solves the "needs web search **and** strict JSON" problem by splitting into a 2-step `SequentialAgent` (Researcher with Tavily → Synthesizer with `output_schema`).

---

## 📁 Project Structure

```text
3rdProject/
├── finsight_agent/
│   ├── __init__.py              # ADK Web package entrypoint
│   └── agent.py                 # root_agent + PDF upload handling for `adk web`
├── agents/
│   ├── orchestrator.py          # InvestmentCommitteeLead (root LlmAgent)
│   ├── extractor_agent.py       # FinancialExtractorAgent (FinancialSnapshot)
│   ├── quant_agent.py           # QuantValuationAgent (ValuationModel)
│   └── qual_agent.py            # QualitativeDiligenceTeam (SequentialAgent)
├── tools/
│   ├── pdf_parser.py            # pdfplumber table & MD&A extractor
│   ├── market_data.py           # yfinance live valuation multiples
│   ├── web_search.py            # Resilient Tavily finance search (LangchainTool)
│   └── excel_builder.py         # openpyxl 3-tab formula-driven .xlsx builder
├── schemas.py                   # Flat Pydantic v2 schemas
├── llm_client.py                # IFM K2 Horizon LiteLLM wrapper (session affinity + JSON sanitizer)
├── app.py                       # Optional Streamlit UI
├── requirements.txt             # Python dependencies
└── .env.example                 # Template for IFM_API_KEY and TAVILY_API_KEY
```

---

## 🚀 Quick Start

### 1. Configure Environment Variables
Copy `.env.example` to `.env` and add your keys:
```bash
cp .env.example .env
```
Required keys in `.env`:
```env
IFM_API_KEY="your-ifm-api-key"
IFM_API_BASE="https://api.ifm.ai/v1"
IFM_MODEL="IFM/K2-Horizon-375B-A23B"
TAVILY_API_KEY="your-tavily-api-key"
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run with Google ADK Web UI (Recommended)
```powershell
.\.venv\Scripts\adk.exe web finsight_agent --port 8000
```
Open **http://127.0.0.1:8000**, select `finsight_agent`, attach a quarterly/annual PDF filing, and ask:
> `Evaluate GESHIP.NS using the attached quarterly earnings presentation and export the Excel model to outputs/GESHIP_Valuation_Model.xlsx.`

### 4. Or Run with Streamlit
```powershell
.\.venv\Scripts\streamlit.exe run app.py
```
