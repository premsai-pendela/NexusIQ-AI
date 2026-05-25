<div align="center">

# NexusIQ AI

### Multi-Agent Business Intelligence Platform

*Ask a question in plain English. Get validated insights from SQL, documents, and live web data — in seconds.*

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-8E75B2?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?style=flat-square)](https://groq.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=flat-square&logo=postgresql&logoColor=white)](https://supabase.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-orange?style=flat-square)](https://trychroma.com)

**[🚀 Live Demo](https://nexusiq-ai.com)** · [Quick Start](#quick-start) · [Architecture](#architecture) · [Query Examples](#query-examples)

</div>

---

## What is NexusIQ AI?

NexusIQ AI is a **multi-agent business intelligence system** that answers complex business questions by intelligently combining three data sources:

| Source | What it knows |
|--------|--------------|
| 🗄️ **SQL Database** | 100,000 Supabase sales transactions across 2024 — revenue, products, regions, payment methods |
| 📄 **PDF Documents** | 25 internal documents — quarterly reports, strategic plans, compliance policies |
| 🌐 **Live Web** | Competitor pricing from live retail sources with explicit cache freshness labels |

The system routes each question to the right source(s), runs the agents in parallel, cross-validates numeric facts, and returns a single fused answer — with confidence badges showing how well the sources agree.

---

## Architecture

```
User Question (plain English)
         │
         ▼
┌─────────────────────┐
│    FUSION AGENT     │  ← Deterministic Web routes + LLM routing
│                     │    Gemini 2.5 Flash → Groq fallback otherwise
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
  │  BM25 +   + httpx/BS4
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

The Fusion Agent routes clear competitor-pricing questions deterministically to the Web Agent. Ambiguous or multi-source questions use a two-tier LLM cascade:

```
Clear competitor-pricing query → Web Agent directly
Other query → Gemini 2.5 Flash (primary, rate-limited)
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

**Evidence-aware query routing** — Clear live-pricing requests route deterministically to the Web Agent. Gemini 2.5 Flash classifies ambiguous or multi-source questions, with Groq fallback when needed.

**SQL Agent with auto-correction** — Converts plain English to SQL via multi-model cascade (Gemini → Groq). Auto-corrects typos ("Wset" → "West", "Electrnics" → "Electronics"). Resolves ambiguity ("best product" → "best product by revenue").

**RAG Agent with hybrid search** — Combines BM25 keyword search + vector embeddings for retrieval. Enters agentic comparison mode for "Compare X vs Y" queries — decomposes into sub-queries, retrieves independently, synthesizes.

**Web Agent with controlled LLM usage** — Exact product prices, ranges, extremes, counts, and discount calculations are built directly from product evidence. Interpretive questions such as market positioning still use the LLM. Nine live sources cover five product categories:

| Category | Scrapers |
|----------|---------|
| Electronics | Newegg (BeautifulSoup), Goal Zero (Shopify API) |
| Home Goods | IKEA (JSON API) |
| Sports | Campmor (Shopify API) |
| Food/Supplements | Swanson, NativePath (Shopify API) |
| Clothing | Taylor Stitch, Chubbies, Finisterre (Shopify API) |

The dashboard distinguishes live results, fresh cache, and stale cache. If a live refresh fails, cached pricing is used for at most seven days and the answer discloses its capture time and failed refresh. Sample fallback data is disabled by default and can be enabled only for an explicit demo with `WEB_ALLOW_SAMPLE_FALLBACK=true`. The IKEA scraper uses a direct JSON API path so the deployed container can run without Selenium.

**Cross-validation engine** — Extracts dollar amounts from both SQL answer text and PDF content, normalizes formats ($45.2M vs $45,200,000), and computes match confidence within 10% tolerance.

**Chart builder** — Appears automatically on SQL results with numeric data. Supports bar, line, scatter, pie charts with export to CSV / JSON / Excel.

**Automated test runner** — 105 test queries across 8 categories and 3 difficulty levels. Run with `python run_tests.py`.

---

## Demo

> 🔗 **Live Demo:** [NexusIQ-AI](https://nexusiq-ai.com)

The public demo is deployed on AWS EC2 behind Caddy HTTPS at `nexusiq-ai.com`. GitHub Actions builds the Docker image, pushes it to ECR, and restarts the EC2 container on every push to `main`.

### Screenshots

| Home | SQL + Chat |
|------|-------------|
| ![Home](Screenshots/home.png) | ![SQL Chat](Screenshots/chat-sql.png) |

| Multi-Agent Fusion | Auto Chart |
|--------------------|------------|
| ![Multi-Agent](Screenshots/mutli-agent.png) | ![Chart](Screenshots/chart.png) |

---

**Example interactions:**

```
"What was Q4 2024 revenue?"
→ sql_rag | SQL: $45.2M | RAG: $45.2M | ✅ HIGH confidence

"Compare Q3 and Q4 2024 performance across all metrics"
→ sql_rag | Agentic decomposition into 3 sub-queries | MEDIUM confidence

"What Goal Zero products and prices are available?"
→ web_only | deterministic calculation from Goal Zero evidence | no answer LLM required

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
DATABASE_URL=postgresql://postgres.PROJECT:PASSWORD@POOLER_HOST:6543/postgres
# Optional demo mode only; leave false for evidence-grounded Web answers
WEB_ALLOW_SAMPLE_FALLBACK=false
```

Inspect the Supabase relational source or refresh local document retrieval data:

```bash
python -m database.ingestion_pipeline status
python -m database.ingestion_pipeline refresh-all --dry-run
python -m database.ingestion_pipeline sync-rag
```

Run the app:

```bash
streamlit run main.py
```

Open `http://localhost:8501`

---

## Production Deployment

NexusIQ is deployed as a containerized Streamlit app on AWS:

| Layer | Production choice |
|-------|-------------------|
| Public URL | `https://nexusiq-ai.com` |
| Compute | EC2 `t3.small` running the Streamlit Docker container |
| HTTPS proxy | Caddy reverse proxy to Streamlit on port `8080` |
| Image registry | Amazon ECR |
| CI/CD | GitHub Actions deploys `main` to EC2 |
| Secrets | AWS Secrets Manager for Google, Groq, and database credentials |
| Document archive | S3 PDF archive |
| Traces | CloudWatch trace foundation plus local trace inspector |
| Database | PostgreSQL via the current `DATABASE_URL`; RDS/pgvector is planned |

Local development still uses the same app entry point:

```bash
streamlit run main.py
```

Streamlit Cloud remains available as a backup demo path, but AWS is the primary production deployment.

---

## Automated Testing

```bash
# Fast deterministic validation suite
python -m unittest discover -s tests -v

# Offline SQL/RAG/Web validation harness (no API calls)
python -m evals.offline_eval

# Production-style golden evals
python -m evals.golden_eval --dry-run
python -m evals.golden_eval --limit 3
python -m evals.golden_eval --replay latest
python -m evals.golden_eval --answer-only --delay 8 --retries 1

# Refresh golden expected numbers from configured DATABASE_URL
python -m evals.refresh_golden_truth --dry-run

# Inspect local AI observability traces
python -m observability.inspect_traces --latest
tail -n 30 data/query_traces.jsonl

# Inspect LLM task usage generated across SQL, RAG, Fusion, and Web
python -m observability.inspect_llm_usage

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

See [docs/evaluation.md](docs/evaluation.md) for the difference between unit tests, offline evals, and live multi-agent test runs. See [docs/observability.md](docs/observability.md) for local trace debugging and the LLM task ledger.

**Current deterministic test results: 56/56 passing.**

---

## Ingestion Pipeline

NexusIQ keeps structured sales data, business PDFs, and the ChromaDB vector index in sync through one CLI:

```bash
# Show SQL row counts, PDF inventory, Chroma document count, and cache files
python -m database.ingestion_pipeline status

# Preview document-index refresh without writing Chroma files
python -m database.ingestion_pipeline refresh-all --dry-run

# SQL facts are protected: this reports that Supabase replacement is disabled
python -m database.ingestion_pipeline rebuild-sql

# Rebuild the ChromaDB document index from data/pdfs/
python -m database.ingestion_pipeline rebuild-rag

# Smart-sync only new, changed, or deleted PDFs using the manifest
python -m database.ingestion_pipeline sync-rag --dry-run
python -m database.ingestion_pipeline sync-rag

# Incrementally add or replace one PDF without rebuilding every document
python -m database.ingestion_pipeline add-pdf --path data/pdfs/01_financial/example.pdf --category 01_financial

# Preserve Supabase SQL facts and rebuild local RAG
python -m database.ingestion_pipeline refresh-all

# Remove local runtime caches only
python -m database.ingestion_pipeline clear-caches
```

Use `sync-rag` for everyday document folder updates. It hashes PDFs, skips unchanged files, updates new or edited PDFs, removes chunks for deleted PDFs, and bumps the ingestion version only when something changed. Use `rebuild-rag` when you want a clean full reset from all PDFs.

`DATABASE_URL` is the only supported relational data source and should point to Supabase PostgreSQL. `refresh-all` preserves those SQL facts and rebuilds only generated local RAG state. Do not commit runtime/cache outputs from `data/chroma_db/`, including `data/chroma_db/ingestion_version.json` and `data/chroma_db/pdf_manifest.json`, `data/web_cache.json`, `data/quota_tracker.json`, `data/llm_task_ledger.jsonl`, `data/query_traces.jsonl`, `traces/`, `eval-reports/`, or `.gstack/` unless you intentionally want to update a tracked baseline.

### Enterprise Data Expansion

The deployed 2024 Supabase dataset remains the validated truth baseline. A
separate generator creates versioned, linked staging extracts for a larger
2021-through-June-2026 retail scenario without connecting to Supabase or
overwriting live tables:

```bash
# Inspect the intended 5-million-transaction portfolio dataset
python -m database.generate_enterprise_expansion plan --profile portfolio

# Produce a smaller local staging dataset first
python -m database.generate_enterprise_expansion generate --profile pilot
python -m database.generate_enterprise_expansion validate --dataset-dir data/expansion/enterprise_pilot_v1
```

The portfolio profile includes customers, products, stores, vendors,
promotions, transactions, returns, inventory snapshots, support cases, and a
business-event timeline. Its future five-million-row sales view is composed
of the untouched 100,000-row live 2024 baseline plus 4,900,000 generated rows
outside 2024, so current PDF cross-validation remains valid. Generated files
are ignored under `data/expansion/`; they must eventually be loaded into a
dedicated staging namespace and validated before any reviewed production promotion. See
[docs/data_expansion_plan.md](docs/data_expansion_plan.md).

The generator validates linked staged rows and rejects generated sales inside
the protected 2024 PDF-aligned period. New reporting-year PDFs must be
generated from staged SQL aggregates and pass SQL-to-PDF golden evaluation
before the expanded data can replace the live query source.

Review the isolated Supabase staging load locally before approving any remote
write:

```bash
python -m database.load_enterprise_staging plan --dataset-dir data/expansion/enterprise_pilot_v1
python -m database.load_enterprise_staging ddl --dataset-dir data/expansion/enterprise_pilot_v1
```

The execution command is locked behind an explicit staging-only confirmation
token and loads only `nexusiq_expansion_staging`; it does not modify existing
public production tables. Load the pilot dataset before the full portfolio
extract.

Plan the next SQL-to-PDF evidence step without connecting to Supabase or
writing documents:

```bash
python -m database.generate_pilot_financial_pdfs plan
python -m database.generate_pilot_financial_pdfs sql
```

The pilot document generator is locked to direct generated tables in
`nexusiq_expansion_staging` for `enterprise_pilot_v1`; it never reads the
combined view containing public live rows and excludes the protected 2024
reporting year. When separately approved, generation requires the
acknowledgement token `GENERATE_PILOT_PDFS_FROM_STAGING_ONLY` and atomically
publishes all new-period PDFs under the repository-owned
`data/pdfs_staging/enterprise_pilot_v1/validated_v2/01_financial/` directory, outside the
existing `data/pdfs/` archive and local RAG index.
Only `validated_v2` is eligible for pilot indexing; older staged pilot
document folders are superseded and must remain unindexed.

After staged PDFs have been separately reviewed, inspect the isolated pilot
RAG and alignment work without opening Chroma or the database:

```bash
python -m database.pilot_document_phase plan-ingestion
python -m database.pilot_document_phase plan-alignment
python -m database.pilot_document_phase plan-index-alignment
```

Execution remains gated. PDF-to-SQL validation can be run independently, and
is also required inside ingestion before the isolated index can be published:

```bash
python -m database.pilot_document_phase validate-alignment \
  --execute-remote \
  --confirm-staging-only VALIDATE_PILOT_PDFS_AGAINST_STAGING_SQL_ONLY

python -m database.pilot_document_phase ingest \
  --execute \
  --confirm-staging-only INGEST_PILOT_PDFS_TO_ISOLATED_STAGING_ONLY \
  --confirm-pdf-validation VALIDATE_PILOT_PDFS_AGAINST_STAGING_SQL_ONLY

python -m database.pilot_document_phase validate-index-alignment \
  --execute-remote \
  --confirm-staging-only VALIDATE_PILOT_STAGING_INDEX_AGAINST_STAGING_SQL_ONLY
```

Pilot ingestion writes only to
`data/chroma_staging/enterprise_pilot_v1/validated_v2/financial_documents/` in the
separate `nexusiq_pilot_financial_docs_enterprise_pilot_v1_validated_v2` collection,
published atomically only after PDF headline revenue and transaction totals pass.
The final index-alignment validation proves that evidence retrieved from this
isolated staged index matches direct staging SQL aggregates.
Production PDFs, `data/chroma_db/`, and the live `nexusiq_docs` RAG collection
remain untouched until staging SQL-to-PDF/index validation passes.

### Enterprise Pilot Demo Mode

The Fusion Agent page now has two explicit evidence workspaces:

- `Live Baseline (2024)` continues to use the production Supabase transaction table,
  the `nexusiq_docs` collection, and live web pricing.
- `Enterprise Pilot (Validated Staging)` uses only the read-only
  `nexusiq_expansion_staging.combined_sales_transactions_enterprise_pilot_v1_793cb277`
  view and the isolated
  `nexusiq_pilot_financial_docs_enterprise_pilot_v1_validated_v2` collection.

Pilot mode displays the verified 250,000-transaction / $340.66M combined
staging scale and guided FY 2021-FY 2023, FY 2025, and H1 2026 evidence
questions. It disables Web routing and refuses to treat production documents
as pilot evidence. The live experience remains the default.

The pilot PDFs and Chroma index are ignored runtime artifacts rather than Git
assets. The EC2 deployment script provisions them in dedicated persistent
Docker volumes before replacing the running app container and re-runs
PDF-to-SQL and index-to-SQL validation on each deployment. If a partial pilot
artifact set is found, deployment fails rather than overwriting evidence
automatically.

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
| Transactions | 100,000 |
| Revenue | ~$175.16M |
| Time Period | Jan 2024 – Dec 2024 |
| Regions | East, West, North, South, Central |
| Categories | Electronics, Clothing, Food, Home, Sports |
| Payment Methods | Credit Card, Debit Card, Digital Wallet, Cash |
| PDF Documents | 25 (quarterly reports, strategy, compliance, policies) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM (Primary) | Gemini 2.5 Flash |
| LLM (Fallback) | Groq Llama 3.3 70B |
| LLM (Local) | Ollama |
| SQL Engine | PostgreSQL (Supabase) · SQLAlchemy |
| Vector DB | ChromaDB |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| BM25 Search | `rank_bm25` |
| Web Scraping | httpx, BeautifulSoup, Shopify APIs |
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
│   └── ingestion_pipeline.py # SQL/RAG refresh workflow
├── observability/
│   └── tracer.py            # Local + CloudWatch trace hooks
├── evals/
│   └── golden_eval.py       # Production-style golden eval runner
├── data/
│   └── chroma_db/           # Vector store
├── run_tests.py             # Automated test runner
├── test_queries.txt         # 105 test queries across 8 categories
└── main.py                  # Entry point
```

---

## Author

**Naga Prem Sai Pendela**
GitHub: [premsai-pendela](https://github.com/premsai-pendela)
