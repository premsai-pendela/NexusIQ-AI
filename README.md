<div align="center">

# NexusIQ AI

### Production Multi-Agent Business Intelligence System

*Ask a business question in plain English. Get validated, cited answers from SQL, documents, and live web data — in seconds.*

[![CI](https://github.com/premsai-pendela/NexusIQ-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/premsai-pendela/NexusIQ-AI/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-4A90E2?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.51+-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-8E75B2?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?style=flat-square)](https://groq.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=flat-square&logo=postgresql&logoColor=white)](https://supabase.com)
[![AWS](https://img.shields.io/badge/AWS-EC2_+_ECR-FF9900?style=flat-square&logo=amazonaws&logoColor=white)](https://aws.amazon.com)

**[🚀 Live Demo](https://nexusiq-ai.com)** · **[📡 REST API](https://nexusiq-ai.com/api/v1/docs)** · **[🎯 Demo Guide](docs/DEMO.md)** · [Quick Start](#quick-start) · [Architecture](#architecture) · [Query Examples](#query-examples)

</div>

---

## What is NexusIQ AI?

NexusIQ AI is a **production-deployed, multi-agent business intelligence system** that answers complex business questions by autonomously searching across three scattered data sources, cross-validating facts, and returning a single fused answer with a confidence score and citations.

| Source | What it knows |
|--------|--------------|
| 🗄️ **SQL Database** | 100,000 transactions in Supabase PostgreSQL — revenue, products, regions, payment methods (FY 2024) |
| 📄 **43 Business PDFs** | Quarterly reports, strategic plans, SOPs, incident reports, policy docs, analyst memos — 425 ChromaDB chunks |
| 🌐 **Live Web** | Competitor pricing across 5 product categories via 9 live scrapers |

The system routes each question to the right source(s), runs agents in parallel, cross-validates numeric facts between SQL answers and PDF text, and returns one answer — with confidence badges showing how well sources agree.

**Key metrics:**
- RAG retrieval: **97.7% Hit@5** · **0.919 Context Recall** · **0.778 MRR**
- Cross-validation precision: **0.03% SQL↔PDF delta** on matching facts
- Multi-source query latency: **5–12 seconds**
- Repeat queries (cached): **< 100ms**
- Test coverage: **194 unit + contract tests**, **12 golden eval cases**, **43-query RAG benchmark**
- LLM cost: **75% fewer LLM calls** on simple SQL queries, **52% fewer tokens** on SQL+RAG validation — proven with before/after ledger profiles
- Text-to-SQL business accuracy: **2/10 → 10/10** on ambiguous business-metric questions via deterministic business-context injection

---

## Architecture

```
User Question (plain English)
         │
         ▼
┌──────────────────────────────┐
│ PRODUCTION HARNESS + GRAPH   │  ← Harness default, LangGraph primary engine
│   Stateful node-by-node      │    Fallback: native harness, then legacy FusionAgent
│   orchestration with         │    Opt out: NEXUSIQ_USE_PRODUCTION_HARNESS=false
│   controlled error paths     │
└──────────────┬───────────────┘
               │
         ┌─────▼──────┐
         │   ROUTING   │  ← Gemini 2.5 Flash → Groq Llama 3.3 70B fallback
         │  + RESOLVE  │    Circuit breaker prevents quota spirals
         └──────┬──────┘
                │  (parallel via ThreadPoolExecutor)
     ┌──────────┼──────────┐
     ▼          ▼          ▼
  🗄️ SQL     📄 RAG     🌐 WEB
  Agent      Agent      Agent
  │          │          │
  Supabase   Hybrid     Shopify API
  PostgreSQL BM25 +     + httpx
  sqlglot    Vector     + BeautifulSoup
  safety     + Reranker
     │          │          │
     └──────────┴──────────┘
                │
                ▼
     ┌──────────────────────┐
     │   FUSION + VALIDATE  │  ← Cross-validates SQL ↔ PDF numbers
     │   HIGH / MED / LOW   │    Deterministic for HIGH confidence
     │   confidence scoring │    LLM synthesis only when needed
     └──────────┬───────────┘
                │
                ▼
         Fused Answer
         + Confidence badge
         + Source citations
         + Observability panel
         + Chart (SQL results)
```

### Production Harness + LangGraph Orchestration

NexusIQ uses a **production agent harness** as the default controller and **LangGraph** as the primary workflow engine inside that harness. The graph formalizes the SQL/RAG/Web/validation workflow into typed, testable nodes:

```
cache_lookup → route_question → resolve_question →
  [sql_node | rag_node | web_node | comparison_node]
→ validation_node → answer_node → cache_admission → finalize
```

Fallback order is production-first: LangGraph workflow → native harness workflow → legacy direct FusionAgent flow. Opt-out flags are available for debugging (`NEXUSIQ_USE_LANGGRAPH=false`, `NEXUSIQ_USE_PRODUCTION_HARNESS=false`), but the normal app path uses the production layer.

### Routing Logic

```
Clear competitor-pricing query  → web_only  (deterministic, no LLM router)
Revenue/cross-source query      → sql_rag   (cross-validation)
Policy/compliance/strategy      → rag_only
Full business analysis          → all       (SQL + RAG + Web)
Out-of-range / unanswerable     → no_data   (safe refusal)

LLM router fallback chain:
  Gemini 2.5 Flash (primary)
    │ quota exhausted?
    ▼
  Groq Llama 3.3 70B (fallback)
```

| Route | When |
|-------|------|
| `sql_only` | Rankings, breakdowns, trends, counts |
| `rag_only` | Policies, strategy, compliance, SOPs |
| `web_only` | Competitor pricing |
| `sql_rag` | Quarterly/annual revenue (cross-validates PDF reports) |
| `sql_web` / `rag_web` / `all` | Multi-source fusion queries |
| `no_data` | Out-of-range dates, unanswerable queries |

---

## Key Features

**LangGraph orchestration** — Production-grade typed state graph formalizes SQL/RAG/Web/validation as named, testable nodes. Conditional routing, controlled error paths, and clean state management. Original FusionAgent preserved as rollback.

**FastAPI REST API + MCP Server** — Programmatic access alongside the Streamlit UI. See [API & MCP](#api--mcp-server) section.

**SQL Agent with auto-correction and parser guardrails** — Converts plain English to SQL via Gemini → Groq cascade. Auto-corrects typos ("Wset" → "West"). Resolves ambiguity ("best product" → "best product by revenue"). Generated SQL is parsed with `sqlglot` — only read-only `SELECT`/`WITH` statements execute; `DROP`, `DELETE`, `ALTER`, and multi-statement queries are rejected at the AST level, not keyword matching.

**Business Context Layer for Text-to-SQL** — Enterprise Text-to-SQL fails because models don't know company definitions ("net revenue", "active customer", "open case"). NexusIQ retrieves company-specific metric definitions deterministically (alias + keyword scoring, no embeddings, no extra LLM calls) and injects only the relevant ones into SQL generation. Measured on 10 ambiguous business questions with live SQL generation + execution: **2/10 correct before → 10/10 after**, with 2 control questions proving plain queries stay byte-identical. Retrieved context IDs appear in the ledger, trace, and UI. Kill switch: `NEXUSIQ_BUSINESS_CONTEXT=0`. Details: [docs/business_context_layer.md](docs/business_context_layer.md).

**RAG Agent with hybrid search + reranker** — Combines BM25 keyword + vector embeddings for first-pass retrieval (43 PDFs, 425 chunks). Cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`) re-scores top-20 candidates for precision. Adaptive HyDE: generates a hypothetical answer to improve retrieval only when confidence score falls below threshold (zero LLM cost on normal queries). Agentic comparison mode decomposes "Compare X vs Y" into sub-queries.

**Web Agent with controlled LLM usage** — Exact product prices, ranges, extremes, counts, and discounts are computed deterministically from scraped evidence (no LLM). Interpretive questions use a compact filtered prompt. Named-competitor questions use that competitor's evidence only. Nine live sources across five categories:

| Category | Sources |
|----------|---------|
| Electronics | Newegg (BeautifulSoup), Goal Zero (Shopify API) |
| Home Goods | IKEA (JSON API) |
| Sports | Campmor (Shopify API) |
| Food/Supplements | Swanson, NativePath (Shopify API) |
| Clothing | Taylor Stitch, Chubbies, Finisterre (Shopify API) |

**Cross-validation engine** — Extracts dollar amounts from SQL answer text and PDF content, normalizes formats (`$45.2M` vs `$45,200,000`), and computes match confidence. HIGH (< 1% diff), MEDIUM (< 10%), LOW (> 10% or conflict). HIGH-confidence answers are formatted deterministically — no extra LLM call. LLM synthesis fires only on conflict or ambiguity.

**Production agent harness** — Default controlled execution layer with bounded steps, per-step task state, retries on transient failures, LangGraph as the primary workflow engine, native harness fallback, and harness metadata in traces.

**Evaluation system** — 194 unit + contract tests, 7 offline eval cases (no API calls), 12 live golden eval cases with rule-based + optional LLM-judge scoring, 43-query RAG benchmark (97.7% Hit@5). Golden truth auto-refreshes from live Supabase.

**Observability** — Every query produces a local JSON trace (route, agent spans, latency, model, confidence, slow-span warnings). Compact JSONL index for terminal inspection. LLM gateway logs task, model, latency, and estimated tokens for every model call. Langfuse mirrors safe metadata automatically when keys are present. AWS CloudWatch in production.

**LLM cost optimization, measured before/after** — Every model call is instrumented first (task, tokens, latency, trace ID), then unnecessary calls were replaced with deterministic logic: rule-based routing for obvious questions, deterministic SQL answer formatting, and deterministic SQL explanations. Avoided calls are logged to the ledger and trace with the reason and the prompt tokens that were never sent. Measured on the same queries under measurement profiles:

| Query | LLM calls before → after | Est. tokens before → after |
|-------|--------------------------|----------------------------|
| Simple SQL count | 4 → **1** (−75%) | 2,036 → **939** (−54%) |
| SQL + RAG validation | 7 → **2** (−71%) | 5,132 → **2,478** (−52%) |

Cross-validation confidence is unchanged (HIGH on matching facts) because validation reads structured SQL rows, not formatted text. `NEXUSIQ_SQL_FORMAT_MODE=llm` / `NEXUSIQ_SQL_EXPLAIN_MODE=llm` restore LLM rendering for A/B comparison. Full methodology and evidence: [docs/llm_cost_optimization.md](docs/llm_cost_optimization.md).

**Conversation memory + query resolution** — Rolls last 5 turns for context-aware follow-ups. Short/ambiguous follow-ups ("q1?") are expanded to standalone questions before hitting SQL/RAG/Web agents. Self-contained questions bypass rewriting to prevent context pollution.

**Dynamic ingestion pipeline** — CLI for status, incremental PDF add/replace, smart sync, and cache management. BM25 index auto-refreshes on document changes in a running app.

**Chart builder** — Appears automatically on SQL results with numeric data. Supports bar, line, scatter, pie with export to CSV / JSON / Excel / Markdown.

---

## API & MCP Server

### REST API (FastAPI)

The REST API runs alongside the Streamlit UI on the same EC2 container.

**Base URL:** `https://nexusiq-ai.com/api/v1`
**Swagger UI:** `https://nexusiq-ai.com/api/v1/docs`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health — SQL ping, Chroma count, agent status |
| `/agents/status` | GET | Per-agent status and model info |
| `/metrics` | GET | Request counts, latency, cache hit rate |
| `/query` | POST | Full fusion query (SQL + RAG + Web) with confidence + route |
| `/query/stream` | POST | SSE streaming — per-agent progress events |
| `/sql` | POST | SQL-only natural language query |
| `/rag` | POST | Document-only semantic search |

```bash
# Example: full fusion query
curl -X POST https://nexusiq-ai.com/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What was Q4 2024 Electronics revenue?"}'

# Response includes: answer, confidence, route, cached, sources, trace_id
```

### MCP Server

NexusIQ exposes four tools via the Model Context Protocol — usable in Claude Desktop, Cursor, VS Code Copilot, and Zed.

| Tool | Use for |
|------|---------|
| `query_database` | Exact SQL-only totals, rankings, counts, breakdowns |
| `search_business_documents` | PDF-only evidence retrieval with citations |
| `query_business_intelligence` | SQL + PDF cross-validation with confidence score |
| `get_competitor_pricing` | Live competitor pricing across 5 categories |

**Claude Desktop setup:**
```json
{
  "mcpServers": {
    "nexusiq": {
      "command": "/path/to/NexusIQ-AI/.venv311/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1"
      }
    }
  }
}
```

---

## Demo

> 🔗 **Live App:** [nexusiq-ai.com](https://nexusiq-ai.com)
> 📡 **API Docs:** [nexusiq-ai.com/api/v1/docs](https://nexusiq-ai.com/api/v1/docs)

### Screenshots

| Home | SQL + Chat |
|------|-------------|
| ![Home](Screenshots/home.png) | ![SQL Chat](Screenshots/chat-sql.png) |

| Multi-Agent Fusion | Auto Chart |
|--------------------|------------|
| ![Multi-Agent](Screenshots/mutli-agent.png) | ![Chart](Screenshots/chart.png) |

### Example interactions

```
"What was Q4 2024 revenue?"
→ sql_rag | SQL: $59.3M | RAG: $59.3M | ✅ HIGH confidence | deterministic format

"Validate Q4 Electronics revenue across SQL and PDF reports"
→ sql_rag | SQL: $31,270,715 | RAG: $31.3M | ✅ HIGH (0.03% delta) | no LLM synthesis

"What Goal Zero products and prices are available?"
→ web_only | deterministic calculation from Goal Zero evidence | Answer method: Calculated

"Compare Q3 and Q4 2024 performance across all metrics"
→ sql_rag | agentic decomposition into sub-queries | sources cited

"What was revenue in 2020?"
→ no_data | "Data covers 2024 only. SQL and RAG cannot answer this."

"Wset region revenue?"
→ auto-corrected to "West region" | sql_rag | answer returned

"What is the return policy?"
→ rag_only | Returns_Refunds_Policy.pdf | 30-day window, category rules, holiday extension
```

---

## Quick Start

```bash
git clone https://github.com/premsai-pendela/NexusIQ-AI.git
cd NexusIQ-AI

python3.11 -m venv .venv311
source .venv311/bin/activate   # Windows: .venv311\Scripts\activate

pip install -r requirements.txt
```

Create `.env`:

```env
GOOGLE_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=postgresql://postgres.PROJECT:PASSWORD@POOLER_HOST:6543/postgres

# Production defaults are already on. These are optional debug overrides:
# NEXUSIQ_USE_PRODUCTION_HARNESS=false
# NEXUSIQ_USE_LANGGRAPH=false
# NEXUSIQ_LANGFUSE_ENABLED=0
WEB_ALLOW_SAMPLE_FALLBACK=false
```

Check data state and sync documents:

```bash
python -m database.ingestion_pipeline status
python -m database.ingestion_pipeline sync-rag --dry-run
python -m database.ingestion_pipeline sync-rag
```

Run the app:

```bash
# Streamlit UI
streamlit run main.py

# FastAPI + Streamlit (same as production)
sh -c 'uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 & streamlit run main.py --server.port 8080'
```

Open `http://localhost:8501` (UI) or `http://localhost:8000/docs` (API).

---

## Production Deployment

NexusIQ runs as a containerized dual-service app on AWS EC2.

| Layer | Production |
|-------|------------|
| Public URL | `https://nexusiq-ai.com` |
| API URL | `https://nexusiq-ai.com/api/v1` |
| Compute | EC2 `t3.small` — Docker container (linux/amd64) |
| Services | Streamlit (port 8080) + FastAPI/uvicorn (port 8000) in one container |
| HTTPS | Caddy reverse proxy — Streamlit at `/`, API at `/api/*` |
| Image registry | Amazon ECR |
| CI/CD | GitHub Actions → ECR push → EC2 deploy on every push to `main` |
| Secrets | AWS Secrets Manager (Gemini, Groq, database, Langfuse) |
| Document archive | S3 PDF archive |
| Observability | CloudWatch logs + local traces + LLM task ledger |
| Database | Supabase PostgreSQL (all envs hit same DB — no data drift) |

### Production Agent Architecture

The deployed app runs the production path by default:

```
Request
  → Production Agent Harness
  → LangGraph workflow
  → SQL / RAG / Web agents
  → Cross-source validation
  → Fused answer
  → Local trace + LLM ledger + Langfuse metadata
```

Fallback order:

1. LangGraph workflow inside the harness.
2. Native harness workflow if LangGraph errors.
3. Legacy direct FusionAgent flow if the production layer errors.

Production safeguards:

- Harness step tracking and bounded execution.
- Parser-based SQL guardrails with `sqlglot`.
- Cache-first behavior for repeated questions.
- One root trace per user query, with LangGraph workflow spans nested inside the harness trace.
- Local JSON traces in `traces/`.
- LLM call ledger in `data/llm_task_ledger.jsonl`.
- Langfuse tracing when keys are present.
- AWS Secrets Manager for deployment secrets.

Debug opt-outs are available but should not be used for normal production:

```bash
NEXUSIQ_USE_PRODUCTION_HARNESS=false
NEXUSIQ_USE_LANGGRAPH=false
NEXUSIQ_LANGFUSE_ENABLED=0
```

```bash
# CI/CD: one command ships to production
git push origin main
```

### Production Health And Smoke Checks

Run these after local startup or after EC2 deployment.

```bash
# Local FastAPI default
python scripts/production_health_check.py --base-url http://localhost:8000
python scripts/production_smoke_test.py --base-url http://localhost:8000

# Public EC2/Caddy URL
python scripts/production_health_check.py --base-url https://nexusiq-ai.com
python scripts/production_smoke_test.py --base-url https://nexusiq-ai.com
```

If `NEXUSIQ_API_KEYS` is enabled in production, pass the key without printing it:

```bash
export NEXUSIQ_API_KEY="your-api-key"
python scripts/production_health_check.py --base-url https://nexusiq-ai.com
python scripts/production_smoke_test.py --base-url https://nexusiq-ai.com
```

On EC2, the same scripts can run from the repo directory against localhost:

```bash
python scripts/production_health_check.py --base-url http://localhost:8000
python scripts/production_smoke_test.py --base-url http://localhost:8000
```

---

## Testing & Evaluation

```bash
# Full deterministic test suite (194 tests)
python -m unittest discover -s tests -v

# Offline eval harness (no LLM/DB calls)
python -m evals.offline_eval

# Production golden evals
python -m evals.golden_eval --dry-run
python -m evals.golden_eval --limit 3
python -m evals.golden_eval --limit 3 --with-judge
python -m evals.golden_eval --answer-only --delay 8 --retries 1
python -m evals.golden_eval --replay latest

# RAG retrieval benchmark (43 queries — Hit@5, MRR, Context Recall)
python -m evals.rag_eval
python -m evals.rag_eval --quick

# Refresh golden truth from live Supabase
python -m evals.refresh_golden_truth --dry-run
python -m evals.refresh_golden_truth

# Business context layer before/after eval (live SQL generation + execution)
python -m evals.context_eval --mode both
python -m evals.context_eval --mode after --ids net_revenue_q4
```

**Current results:**
- Unit + contract tests: **194/194 passing**
- Offline evals: **7/7 passing**
- RAG benchmark: **97.7% Hit@5 · 0.919 Context Recall · 0.778 MRR**

See [docs/evaluation.md](docs/evaluation.md) for the difference between unit tests, offline evals, and live golden evals.

---

## Observability

```bash
# Inspect latest query trace
python -m observability.inspect_traces --latest
python -m observability.inspect_traces --latest --json

# Quick terminal scan (JSONL index)
tail -n 30 data/query_traces.jsonl

# LLM task usage (task, model, latency, tokens)
tail -n 20 data/llm_task_ledger.jsonl

# Aggregated LLM usage report — per-task/model/profile tokens, latency,
# fallbacks, and avoided calls (deterministic paths that skipped an LLM call)
python -m observability.inspect_llm_usage
python -m observability.inspect_llm_usage --json
```

Every answer includes a "How NexusIQ Ran This Answer" panel in the UI showing route, total time, validation confidence, router model, slowest span, and trace ID.

See [docs/observability.md](docs/observability.md) for Langfuse setup and CloudWatch integration.

**Engineering post-mortems:** [docs/postmortems.md](docs/postmortems.md) — real defects found while operating the system (duplicate root traces, a guardrail false-positive, markdown-blind validation, ContextVar loss across thread pools), each with root cause, fixing commit, and the regression tests that now guard it.

---

## Ingestion Pipeline

```bash
# Show SQL row counts, PDF inventory, Chroma count, cache files
python -m database.ingestion_pipeline status

# Smart-sync only new, changed, or deleted PDFs
python -m database.ingestion_pipeline sync-rag --dry-run
python -m database.ingestion_pipeline sync-rag

# Incrementally add or replace one PDF
python -m database.ingestion_pipeline add-pdf \
  --path data/pdfs/01_financial/example.pdf \
  --category 01_financial

# Full Chroma rebuild from all PDFs
python -m database.ingestion_pipeline rebuild-rag

# Preview without writing
python -m database.ingestion_pipeline refresh-all --dry-run

# Remove local runtime caches only
python -m database.ingestion_pipeline clear-caches
```

Use `sync-rag` for everyday updates — hashes PDFs, skips unchanged files, removes stale chunks, auto-bumps ingestion version. BM25 index refreshes automatically in a running app on the next query after a version change.

---

## Query Examples

### SQL Only
```
What is the total 2024 revenue?
Top 5 products by revenue                    → bar chart
Show sales by region                         → bar chart
Monthly sales trend for 2024                 → line chart
Payment method distribution                  → pie chart
Which store in the East region performed best?
```

### RAG Only
```
What is the return policy?
What are the Q4 2024 strategic priorities?
What is the Digital Wallet initiative?
Summarize the inventory reorder SOP
What happened during the Black Friday incident?
```

### Web Only
```
What are competitor prices for electronics?
What Goal Zero products and prices are available?
Show discounted clothing products and original prices
Price range for camping gear at competitors?
```

### SQL + RAG (Cross-Validation)
```
What was Q4 2024 revenue?
Validate Q4 Electronics revenue across SQL and PDF reports
Compare Q3 and Q4 2024 revenue with full validation
Annual 2024 revenue — validate across sources
```

### All Sources
```
Complete Q4 2024 analysis: validate revenue, compare competitor pricing, assess strategy
Full business intelligence: quarterly numbers, strategic goals, competitor benchmarks
Explain why West region outperformed South in 2024
```

### Edge Cases
```
"Wset region revenue?"         → auto-corrected to "West"
"Electrnics sales?"            → inferred as "Electronics"
"Revenue in 2020?"             → no_data (data covers 2024 only)
"Best product?"                → auto-resolved to "by revenue"
"q1?" (after prior Q4 query)  → resolved to "Q1 2024 Electronics revenue"
```

---

## Dataset

| Attribute | Value |
|-----------|-------|
| Transactions | 100,000 |
| Revenue | $175,595,178 |
| Time Period | Jan 2024 – Dec 2024 |
| Regions | East, West, North, South, Central |
| Categories | Electronics, Clothing, Food, Home, Sports |
| Payment Methods | Credit Card, Debit Card, Digital Wallet, Cash |
| Seasonal pattern | Q1 $26.9M → Q4 $59.3M (realistic retail distribution) |
| PDF Documents | 43 (quarterly reports, SOPs, incident reports, analyst memos, policy docs) |
| ChromaDB chunks | 425 |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph (StateGraph, typed nodes, conditional edges) |
| LLM (Primary) | Gemini 2.5 Flash |
| LLM (Fallback) | Groq Llama 3.3 70B |
| LLM (Local dev) | Ollama |
| REST API | FastAPI + uvicorn + slowapi |
| MCP Server | fastmcp (4 tools) |
| SQL Engine | PostgreSQL (Supabase) · SQLAlchemy · sqlglot (parser safety) |
| Vector DB | ChromaDB (cosine distance) |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers, 384 dim) |
| Reranker | `ms-marco-MiniLM-L-6-v2` (cross-encoder, ~22MB CPU) |
| BM25 | `rank_bm25` |
| Web Scraping | httpx · BeautifulSoup · Shopify JSON API |
| Frontend | Streamlit 1.51+ |
| Charts | Plotly |
| Data | Pandas · NumPy |
| Containerization | Docker (linux/amd64) |
| Cloud | AWS EC2 · ECR · S3 · Secrets Manager · CloudWatch |
| CI/CD | GitHub Actions |
| HTTPS | Caddy + Let's Encrypt |
| DNS | Cloudflare |
| Observability | Local JSON traces · JSONL ledger · Langfuse (optional) · CloudWatch |

---

## Project Structure

```
NexusIQ-AI/
├── agents/
│   ├── fusion_agent.py        # Original orchestration (rollback path)
│   ├── fusion_graph.py        # LangGraph orchestration (production)
│   ├── _singleton.py          # Shared agent instances (FastAPI + Streamlit)
│   ├── production_harness.py  # Bounded controller + task state
│   ├── sql_agent.py           # NL → SQL → answer (sqlglot safety)
│   ├── rag_agent.py           # Hybrid BM25 + vector + reranker
│   └── web_agent.py           # Competitor scraping (9 sources)
├── api/
│   ├── main.py                # FastAPI app + lifespan pre-warm
│   ├── routes/
│   │   ├── query.py           # POST /query, POST /query/stream (SSE)
│   │   ├── agents.py          # POST /sql, POST /rag
│   │   └── health.py          # GET /health, /agents/status, /metrics
│   ├── models/schemas.py      # Pydantic v2 request/response models
│   └── middleware/auth.py     # API key auth
├── mcp_server/
│   └── server.py              # 4 MCP tools + 2 resources + 1 prompt template
├── config/
│   ├── settings.py            # Pydantic config + feature flags
│   ├── company_data.py        # Single source of truth for business metrics
│   └── data_inventory.py      # RAG routing patterns
├── database/
│   └── ingestion_pipeline.py  # CLI: status, sync-rag, add-pdf, rebuild-*
├── observability/
│   ├── tracer.py              # Local JSON traces + JSONL index + CloudWatch
│   ├── langfuse_adapter.py    # Optional Langfuse integration
│   └── inspect_traces.py      # CLI trace inspector
├── utils/
│   ├── llm_gateway.py         # Centralized model calls + task ledger
│   ├── validators.py          # Typo correction, ambiguity resolution
│   ├── quota_tracker.py       # Circuit breaker
│   └── query_normalization.py # Canonical question matching
├── evals/
│   ├── golden_eval.py         # Live golden eval runner
│   ├── golden_cases.json      # 12 golden cases
│   ├── offline_eval.py        # No-API deterministic harness
│   ├── rag_eval.py            # 43-query RAG benchmark
│   ├── judge.py               # Optional LLM-as-judge
│   └── refresh_golden_truth.py
├── tests/
│   ├── test_validation_contracts.py  # 90+ contract + routing tests
│   ├── test_fusion_graph.py          # LangGraph route tests
│   ├── test_ingestion_pipeline.py    # Ingestion tests
│   ├── test_production_harness.py    # Harness tests
│   ├── test_langfuse_observability.py
│   └── test_sql_safety.py            # sqlglot guardrail tests
├── ui/
│   └── fusion_chat.py         # Streamlit UI + observability panel
├── docs/
│   ├── evaluation.md
│   ├── observability.md
│   └── sql_guardrails.md
├── data/pdfs/                 # 43 business documents (8 categories)
├── Dockerfile                 # linux/amd64, dual-service (uvicorn + streamlit)
├── main.py                    # Streamlit entry point
└── requirements.txt
```

---

## Key Engineering Decisions

| Decision | Rationale |
|----------|-----------|
| LangGraph over custom-only orchestration | Formalizes existing graph-like workflow; typed state, testable nodes, explainable in interviews. Custom FusionAgent preserved as rollback. |
| Hybrid BM25 + vector search | Vector alone misses exact keywords (Q4, Electronics, $31.7M). BM25 catches those; vector catches semantic matches. |
| Cross-encoder reranker | Re-scores top-20 hybrid candidates; higher precision especially when wrong doc type retrieves first. |
| Adaptive HyDE | Checks retrieval confidence before spending an LLM call; normal queries pay zero cost. |
| Deterministic synthesis for HIGH confidence | Formatting validated facts directly is faster, cheaper, more stable than LLM paraphrase. LLM fires only on conflict. |
| sqlglot AST-based SQL safety | Parser understands SQL grammar — distinguishes `created_at` column from `CREATE` command. Regex matching had false positives. |
| ThreadPoolExecutor for parallelism | All agents are I/O-bound. Threads release GIL during I/O. Zero agent code changes. asyncio would require full sync→async rewrite. |
| TTL dict cache | No deps, no infra, bounded memory, auto-expires. Redis overkill for single-user demo. Quality-gated: degraded or low-confidence answers not cached. |
| Delete-then-upsert for PDF ingestion | Upsert alone leaves stale chunks when an edited PDF shrinks. Delete first ensures only fresh chunks remain. |

---

## Future Improvements

- **CSV ingestion** — add CSV files as a first-class data source alongside SQL, PDF, and web
- **Dynamic company onboarding** — upload files, auto-index, query your own company knowledge base
- **Eval dashboard** — pass/fail accuracy, confidence trends, source quality, and regression history
- **Voice input** — speak questions instead of typing (Claude/Codex voice style)
- **Memory layer** — persist useful previous tasks, preferences, and repeated company context across sessions
- **Better error recovery** — more graceful degradation when one source fails mid-query
- **Production deployment polish** — EC2/Docker health checks, monitoring docs, deeper CloudWatch alarms

---

## Author

**Naga Prem Sai Pendela**
[GitHub](https://github.com/premsai-pendela) · [LinkedIn](https://www.linkedin.com/in/nagapremsai-pendela/) · [Portfolio](https://tinyurl.com/naga-portfolio)
