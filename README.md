<div align="center">

# NexusIQ AI

### Multi-Agent Business Intelligence Platform

*Ask a question in plain English. Get validated insights from SQL, documents, and live web data — in seconds.*

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-8E75B2?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?style=flat-square)](https://groq.com)
[![DuckDB](https://img.shields.io/badge/DuckDB-Analytics-FFF000?style=flat-square&logo=duckdb&logoColor=black)](https://duckdb.org)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-orange?style=flat-square)](https://trychroma.com)

**[Live Demo](#demo)** · [Quick Start](#quick-start) · [Architecture](#architecture) · [Query Examples](#query-examples)

</div>

---

## What is NexusIQ AI?

NexusIQ AI is a **multi-agent business intelligence system** that answers complex business questions by intelligently combining three data sources:

| Source | What it knows |
|--------|--------------|
| 🗄️ **SQL Database** | 90,500 sales transactions across 2024 — revenue, products, regions, payment methods |
| 📄 **PDF Documents** | 23 internal documents — quarterly reports, strategic plans, compliance policies |
| 🌐 **Live Web** | Real-time competitor pricing scraped from Newegg, IKEA, Campmor, Swanson |

The system routes each question to the right source(s), runs the agents in parallel, cross-validates numeric facts, and returns a single fused answer — with confidence badges showing how well the sources agree.

---

## Architecture

```
User Question (plain English)
         │
         ▼
┌─────────────────────┐
│    FUSION AGENT     │  ← LLM-based dynamic routing
│                     │    Gemini 2.5 Flash → Groq fallback
│  Classifies intent  │    Rate-limited to prevent quota exhaustion
│  Routes to sources  │
└──────┬──────┬───────┘
       │      │
  ┌────┘  ┌───┘  ┌──────────────────────┐
  │       │      │                      │
  ▼       ▼      ▼                      │
🗄️ SQL  📄 RAG  🌐 WEB              [parallel]
Agent   Agent   Agent
  │       │      │
  │   Hybrid  Shopify API
  │  BM25 +   + Selenium
  │  Vector   + BeautifulSoup
  │  Search
  │       │      │
  └───────┴──────┘
         │
         ▼
┌─────────────────────┐
│  Cross-Validation   │  ← Extracts + compares numbers
│  HIGH / MED / LOW   │    across SQL answers and PDF text
└─────────────────────┘
         │
         ▼
   Fused Answer
   + Chart Builder
   + Source Citations
   + Confidence Badge
```

### Routing Logic

The Fusion Agent uses a two-tier LLM cascade to route every query:

```
Query → Gemini 2.5 Flash (primary, rate-limited)
              │ quota exhausted?
              ▼
         Groq Llama 3.3 70B (fallback)
              │ all sources return false?
              ▼
         "no_data" response (clear message, no hallucination)
```

Six route types:

| Route | When |
|-------|------|
| `sql_only` | Rankings, breakdowns, trends, counts |
| `rag_only` | Policies, strategy, compliance |
| `web_only` | Competitor pricing |
| `sql_rag` | Quarterly/annual revenue (cross-validates PDF reports) |
| `sql_web` / `rag_web` / `all` | Multi-source fusion queries |
| `no_data` | Out-of-range dates, unanswerable queries |

---

## Key Features

**LLM-based query routing** — Gemini 2.5 Flash classifies intent and picks the right combination of agents. Falls back to Groq seamlessly when quota is hit. Shows a warning banner when fallback routing is used.

**SQL Agent with auto-correction** — Converts plain English to SQL via multi-model cascade (Gemini → Groq). Auto-corrects typos ("Wset" → "West", "Electrnics" → "Electronics"). Resolves ambiguity ("best product" → "best product by revenue").

**RAG Agent with hybrid search** — Combines BM25 keyword search + vector embeddings for retrieval. Enters agentic comparison mode for "Compare X vs Y" queries — decomposes into sub-queries, retrieves independently, synthesizes.

**Web Agent with live scraping** — Five competitor scrapers across five product categories:

| Category | Scrapers |
|----------|---------|
| Electronics | Newegg (BeautifulSoup) |
| Home Goods | IKEA (Selenium) |
| Sports | Campmor (Shopify API) |
| Food/Supplements | Swanson, NativePath (Shopify API) |
| Clothing | Taylor Stitch, Chubbies (Shopify API) |

Includes per-scraper status dashboard and cache invalidation for empty results.

**Cross-validation engine** — Extracts dollar amounts from both SQL answer text and PDF content, normalizes formats ($45.2M vs $45,200,000), and computes match confidence within 10% tolerance.

**Chart builder** — Appears automatically on SQL results with numeric data. Supports bar, line, scatter, pie charts with export to CSV / JSON / Excel.

**Automated test runner** — 105 test queries across 8 categories and 3 difficulty levels. Run with `python run_tests.py`.

---

## Demo

> 🔗 **Live Demo:** *coming soon — link will be added after deployment*

**Example interactions:**

```
"What was Q4 2024 revenue?"
→ sql_rag | SQL: $45.2M | RAG: $45.2M | ✅ HIGH confidence

"Compare Q3 and Q4 2024 performance across all metrics"
→ sql_rag | Agentic decomposition into 3 sub-queries | MEDIUM confidence

"What are competitor prices for electronics?"
→ web_only | Newegg live data | 10 products scraped

"What was revenue in 2020?"
→ no_data | "Data only covers 2024. SQL and RAG cannot answer this."

"Wset region revenue?"
→ Auto-corrected to "West region" | sql_rag | answer returned
```

---

## Quick Start

```bash
git clone https://github.com/premsai-pendela/NexusIQ-AI.git
cd NexusIQ-AI

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create `.env`:

```env
GOOGLE_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
DATABASE_PATH=data/sales.db
```

Generate data and run:

```bash
python database/generate_data.py
streamlit run main.py
```

Open `http://localhost:8501`

---

## Automated Testing

```bash
# Run all 105 queries
python run_tests.py

# Run by phase
python run_tests.py --phase 1   # Basic functionality (5 queries)
python run_tests.py --phase 2   # Cross-validation (3 queries)
python run_tests.py --phase 3   # Edge cases (5 queries)
python run_tests.py --phase 4   # Advanced multi-source (6 queries)
python run_tests.py --phase 5   # Chart builder SQL (4 queries)

# Run specific queries
python run_tests.py --ids 46,85,91

# Run a section
python run_tests.py --section "SQL ONLY"

# Dry run (print queries without executing)
python run_tests.py --dry-run
```

Reports are saved to `.gstack/test-reports/` as Markdown + JSON.

**Current test results across all 5 phases: 23/23 passing.**

---

## Query Examples

### SQL Only
```
What is the total revenue?
Top 5 products by revenue                   → Bar chart
Show sales by region                        → Bar chart
Monthly sales trend for 2024               → Line chart
Payment method distribution                → Pie chart
Year-over-year growth rate by quarter
Which store in the East region performed best?
```

### RAG Only
```
What is the return policy?
What are the Q4 2024 strategic priorities?
What is the Digital Wallet initiative?
Compare Q3 and Q4 2024 performance across all metrics
```

### Web Only
```
What are competitor prices for electronics?
How do IKEA's home goods prices compare to ours?
What is the price range for camping gear at competitors?
```

### SQL + RAG Fusion (Cross-Validation)
```
What was Q4 2024 revenue?
Validate Q4 2024 Electronics revenue against reports
Compare Q3 and Q4 revenue with full validation
```

### All Sources
```
Complete Q4 2024 analysis: validate revenue, compare competitor pricing, assess strategy
Full business intelligence: quarterly numbers, strategic goals, competitor benchmarks
```

### Edge Cases
```
What was revenue in Wset region?           → Auto-corrects to "West"
Show me sales for Electrnics               → Infers "Electronics"
What was revenue in 2020?                  → Returns "no data" (data covers 2024 only)
What is the best product?                  → Auto-resolves to "by revenue"
```

---

## Dataset

| Attribute | Value |
|-----------|-------|
| Transactions | 90,500 |
| Revenue | ~$139M |
| Time Period | Jan 2024 – Dec 2024 |
| Regions | East, West, North, South, Central |
| Categories | Electronics, Clothing, Food, Home, Sports |
| Payment Methods | Credit Card, Debit Card, Digital Wallet, Cash |
| PDF Documents | 23 (quarterly reports, strategy, compliance, policies) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM (Primary) | Gemini 2.5 Flash |
| LLM (Fallback) | Groq Llama 3.3 70B |
| LLM (Local) | Ollama |
| SQL Engine | DuckDB |
| Vector DB | ChromaDB |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| BM25 Search | `rank_bm25` |
| Web Scraping | httpx, BeautifulSoup, Selenium |
| Frontend | Streamlit |
| Charts | Plotly |
| Data | Pandas |

---

## Project Structure

```
NexusIQ-AI/
├── agents/
│   ├── fusion_agent.py      # Routing + orchestration
│   ├── sql_agent.py         # NL → SQL → answer
│   ├── rag_agent.py         # Hybrid BM25 + vector retrieval
│   └── web_agent.py         # Competitor scraping
├── ui/
│   └── fusion_chat.py       # Streamlit UI
├── utils/
│   ├── validators.py        # Typo correction, ambiguity resolution
│   └── quota_tracker.py     # Circuit breaker for LLM quotas
├── database/
│   └── generate_data.py     # Synthetic dataset generation
├── data/
│   └── chroma_db/           # Vector store
├── run_tests.py             # Automated test runner
├── test_queries.txt         # 105 test queries across 8 categories
└── main.py                  # Entry point
```

---

## Author

**Prem Sai Pendela**
GitHub: [premsai-pendela](https://github.com/premsai-pendela)
