# NexusIQ AI Project Report

Source scope: Notion `#NPS2 Pro`, related NexusIQ pages, and recent project memory observations through May 19, 2026.

## 1. Executive Summary

NexusIQ AI is a production-minded multi-agent business intelligence system. The core idea is that business answers are unreliable when they come from only one source. NexusIQ answers business questions by routing work across structured SQL data, document RAG, live web intelligence, and a Fusion Agent that combines and validates the result.

The project moved through several clear stages:

1. Build a realistic multi-source BI problem.
2. Implement a SQL Agent for natural language to SQL.
3. Add RAG over business PDFs.
4. Align SQL and PDF data so cross-source validation is meaningful.
5. Build a Fusion Agent that routes, validates, and confidence-scores answers.
6. Add Web Agent competitor intelligence.
7. Improve performance with parallel execution, caching, and progressive status.
8. Add evals and observability so the project can prove and debug its behavior.
9. Add context engineering, conversation memory, query resolution, adaptive retrieval, and dynamic ingestion.
10. Rework the demo experience so recruiters immediately understand the technical depth.
11. Prepare deployment infrastructure, including Streamlit keep-alive and Cloud Run scaffolding.

The final story is not "I built a chatbot." The stronger story is:

> I built a multi-source AI intelligence system that retrieves from several business data layers, validates answers across sources, explains confidence, and includes production-style evaluation, observability, ingestion, and deployment workflows.

## 2. Problem You Chose

The project began with a practical business problem: executives and analysts often need answers that are scattered across databases, reports, spreadsheets, websites, and customer feedback. A normal analyst workflow can take days:

- Query a database.
- Read quarterly reports.
- Check market research.
- Scrape competitor prices.
- Review customer sentiment.
- Combine findings manually.
- Write a stakeholder summary.

NexusIQ compresses that into a guided AI workflow. The system uses specialized agents to gather evidence, then produces a single answer with citations, confidence, and source validation.

### Why This Problem Was Strong

You chose this because it demonstrates applied AI engineering instead of only model usage. The work shows:

- Data engineering: SQL data generation, schema design, ingestion, refresh workflows.
- Retrieval: ChromaDB, embeddings, BM25, hybrid search, HyDE.
- LLM orchestration: Gemini, Groq, Ollama fallback, routing, fusion prompts.
- Product engineering: Streamlit app, guided command center, query history, exports.
- Reliability: evals, traces, circuit breaker, cache, deployment scripts.
- Business sense: revenue questions, regional analysis, competitor pricing, policy lookup.

This makes it better positioned for Applied AI Engineer, AI Application Engineer, GenAI Engineer, Forward Deployed AI Engineer, AI Product Engineer, and AI Solutions Engineer roles than for a pure ML research role.

## 3. Data Strategy

You intentionally used a mix of synthetic and real-world-style data. The decision was not accidental; it was based on privacy, ethics, and system-design goals.

### Structured Data

The SQL layer uses the configured Supabase PostgreSQL database with 100,000 generated sales transactions totaling about $175.16M for 2024. The retired local SQLite snapshot contained an older 90,500-row fixture and is no longer a supported relational source. The data includes:

- Regions: East, West, North, South, Central.
- Product categories: Electronics, Clothing, Food, Home, Sports.
- Stores, customers, payment methods, quantities, prices, and dates.
- Revenue totals and seasonal patterns.

Later, the data was regenerated to reflect realistic retail seasonality:

- Q1: post-holiday slowdown.
- Q2: spring pickup.
- Q3: back-to-school surge.
- Q4: holiday peak.

This fixed the earlier issue where revenue was too flat across quarters.

### Document Data

You generated 25 business PDFs across several categories:

- Financial reports and forecasts.
- Market intelligence.
- Contracts and legal documents.
- Product and operations documents.
- Strategy and expansion plans.
- HR and compliance documents.

The documents were designed to test realistic RAG tasks:

- Specific number lookup.
- Cross-document comparison.
- Policy extraction.
- Contract term extraction.
- Strategic summary.
- Financial context and source citation.

### Web Data

The Web Agent was built for live competitor/product intelligence. It used several collection methods:

- BeautifulSoup for static HTML.
- Selenium/Firefox for JavaScript-heavy sites.
- Shopify JSON APIs where available.
- Mock fallback data where websites blocked automation or were unsuitable.

The important decision here was to avoid fighting hostile anti-bot systems when better data paths existed. For example, Shopify APIs were more reliable than brittle HTML scraping.

### Why Synthetic Data Was Acceptable

You chose synthetic internal data because:

- Real customer and financial data can be private, sensitive, or unethical to expose.
- The project was about building a reusable AI intelligence system, not discovering one real company's secret insight.
- Synthetic data let you control edge cases, date ranges, and cross-source truth.
- The system architecture is data-agnostic and could be pointed at a real company database later.

The strongest interview answer is:

> I used synthetic internal data for privacy and control, but real external-style web and market sources for authenticity. The technical challenge was not the specific customer IDs; it was building an AI system that can integrate SQL, documents, and web data, validate the result, and explain confidence.

## 4. Architecture

The intended architecture is:

```text
User question
  |
  v
Query routing
  |
  +-- SQL Agent: exact structured facts from transaction data
  +-- RAG Agent: context and evidence from documents
  +-- Web Agent: live competitor/product intelligence
  |
  v
Fusion Agent
  |
  +-- combines source outputs
  +-- compares numbers across sources
  +-- assigns confidence
  +-- generates a unified answer
  |
  v
User-facing answer with source evidence
```

The key design principle is source specialization:

- SQL is best for exact counts, sums, groupings, and transaction-level truth.
- RAG is best for reports, policies, contracts, strategy, and context.
- Web is best for competitor or market data.
- Fusion is best for deciding how much to trust the combined answer.

## 5. Major Technical Components

### SQL Agent

The SQL Agent turns plain-English business questions into SQL, runs them safely, and formats the answer.

Important capabilities:

- Natural language to SQL.
- Model routing by query complexity.
- SQL safety validation to reject dangerous operations.
- Transaction rollback on errors.
- Query explanation.
- Query history.
- Cached history replay.
- Multi-format exports.
- Typo, date range, and ambiguity validation.

Key decision criteria:

- Business users should not need to know SQL.
- The agent must avoid dangerous SQL.
- The system should be transparent enough to show the generated query.
- Bad questions should be caught before wasting LLM calls.

### RAG Agent

The RAG Agent searches business documents and answers document-based questions.

Important capabilities:

- PDF text extraction.
- Chunking with overlap.
- Embeddings using `all-MiniLM-L6-v2`.
- ChromaDB vector storage.
- Source citations.
- Hybrid BM25 plus vector retrieval.
- Query decomposition for comparisons.
- Adaptive HyDE when retrieval confidence is weak.
- Agentic comparison for Q3 vs Q4 style questions.

Key decision criteria:

- Vector search alone was not accurate enough for dates, quarters, and exact financial terms.
- BM25 was needed because exact keywords like `Q3`, `Q4`, `Electronics`, and dollar values matter.
- HyDE should be adaptive, not always-on, because every extra LLM call burns quota.
- Unsupported ChromaDB metadata filtering was removed instead of forcing brittle code.

### Web Agent

The Web Agent retrieves competitor/product intelligence.

Important capabilities:

- Multiple scraping strategies.
- Selenium fallback for JavaScript pages.
- Shopify API extraction when available.
- Cache and fallback behavior.
- Integration with Fusion Agent.

Key decision criteria:

- Use APIs when available because they are faster and more reliable than scraping.
- Avoid sites that aggressively block bots when scraper-friendly alternatives exist.
- Keep mock fallback data so demos do not collapse if a website changes.
- Cache results to reduce redundant requests and rate-limit pressure.

### Fusion Agent

The Fusion Agent is the core differentiator. It routes questions, runs the needed agents, validates evidence, and produces a unified answer.

Important capabilities:

- Query classification: SQL-only, RAG-only, Web-only, SQL+RAG, SQL+Web, RAG+Web, all sources.
- Cross-source validation of numbers.
- Confidence levels: HIGH, MEDIUM, LOW.
- Tolerance-based numeric comparison.
- Parallel agent execution.
- Query result caching.
- Progressive UI callbacks.
- Conversation memory.
- Query resolution for short follow-ups.
- Trace creation for observability.

Key decision criteria:

- SQL exact values and PDF rounded values should be treated as matching if they are within tolerance.
- Independent agents should run concurrently because they are I/O-bound.
- A single fused answer is more useful than forcing the user to compare raw source outputs.
- Confidence scoring makes the AI answer more trustworthy.

## 6. Chronological Development Timeline

### Day 1: Foundation

You set up the development environment:

- Gemini API.
- Groq API.
- GCP account.
- HuggingFace account.
- PostgreSQL.
- Ollama.
- Python virtual environment.
- Dependencies.
- GitHub repo.
- `.gitignore`.
- README.

You created the original database schema and generated the first synthetic sales dataset.

Decision criteria:

- Use free or low-cost tools.
- Keep local development possible.
- Make the stack reproducible.
- Protect API keys.

### Day 2: Production-Style SQL Agent

You improved the SQL Agent with:

- Correct model names.
- Gemini/Groq/Ollama fallback.
- Circuit breaker quota tracking.
- Transaction rollback.
- Better error messages.
- Full-screen loading UX.
- Model journey transparency.

Important bug fixes:

- Gemini model name errors.
- Groq model name errors.
- PostgreSQL transaction-aborted state.
- Streamlit page transition flash.
- Stuck tips in the UI.

Decision criteria:

- If a model is quota-blocked, skip it quickly rather than waiting through retry spirals.
- Users should understand why a query is slow.
- Failure should degrade to another provider, not crash the app.

### Day 3: Query Explanation and History

You added:

- LLM-powered SQL explanations.
- Basic fallback explanations.
- Last 10 query history items.
- Cached result viewing.
- Re-run from history.
- Smart `time ago` formatting.

Decision criteria:

- Users trust the system more when they can see how the query works.
- Repeated questions should not waste API calls.
- History is both a UX feature and a debugging aid.

### Day 4: Edge Case Handling

You added question validation:

- Region typo detection.
- Category typo detection.
- Date range validation.
- Ambiguity detection.

You tried to implement auto-retry with corrected text, but Streamlit widget state made it impractical. You tested multiple approaches:

- `value=` parameter.
- Direct `session_state` modification.
- Pre-widget session state.
- Pending fix plus rerun.
- Form-based input.
- Dynamic widget keys.

Final decision:

- Show corrected suggestions clearly instead of forcing text input mutation.

Decision criteria:

- Avoid fighting Streamlit limitations.
- Keep the user experience helpful.
- Save LLM calls by validating before SQL generation.

### Export Options

You added:

- CSV export.
- JSON export.
- Excel export with auto-sized columns.
- Markdown export.
- Result persistence after downloads.

Decision criteria:

- Business users expect Excel.
- Developers may want JSON.
- Documentation workflows may want Markdown.
- Downloading should not erase the displayed result.

### Days 5-7: RAG and Document Intelligence

You built the RAG pipeline:

- Created 25 PDFs.
- Extracted text.
- Chunked documents.
- Embedded chunks.
- Stored them in ChromaDB.
- Built `agents/rag_agent.py`.
- Added citations and adaptive thresholds.

Then you discovered a major retrieval issue:

- Vector search ranked the wrong Q3/Q4 chunks above the correct financial summary.
- Q3 revenue retrieval returned wrong numbers or failed.

You solved it with hybrid search:

- BM25 for exact keyword matching.
- Vector search for semantic meaning.
- Weighted score combination.

Decision criteria:

- Retrieval correctness matters more than prompt cleverness.
- Hardcoded hints are cheating; the retriever should find the correct evidence naturally.
- BM25 plus vector search is a standard production RAG pattern.

### Data Alignment Phase

You found SQL and PDF data were misaligned:

- SQL dates were in the wrong range.
- PDF reports referenced 2024.
- Revenue numbers did not match.

You fixed this by:

- Treating Supabase PostgreSQL as the relational source of truth while retaining `config/company_data.py` only as a guarded legacy synthetic fixture.
- Creating aligned data generation scripts.
- Regenerating SQL data.
- Updating PDF generation.
- Re-ingesting documents into ChromaDB.

Decision criteria:

- Cross-validation is meaningless if sources disagree because of test-data drift.
- One source of truth prevents future mismatch.
- Financial PDFs should be generated from the same truth used by SQL.

### Day 8: Fusion Agent

You built cross-source validation:

- SQL runs exact calculation.
- RAG retrieves report context.
- Fusion compares values.
- Fusion assigns confidence.
- Final answer includes exact value, context, and validation.

Example strong case:

- SQL returns Q4 Electronics revenue.
- PDF report states the rounded value.
- Fusion recognizes the values match.
- Confidence becomes HIGH.

Decision criteria:

- SQL should be trusted for exact numeric precision.
- Documents should be trusted for business context.
- Rounded document numbers should not be treated as contradictions.
- The final answer should tell the user whether sources agree.

## 7. Performance and UX Improvements

### Parallel Agent Execution

Problem:

- Multi-source queries ran SQL, RAG, and Web sequentially.
- Total latency could approach 48 seconds.

Options considered:

- `asyncio.gather`: rejected because agents were synchronous and Streamlit event loops make async refactors risky.
- `multiprocessing`: rejected because LangChain objects and model objects do not pickle cleanly, and process startup would reload heavy models.
- `ThreadPoolExecutor`: chosen because SQL, RAG, and Web calls are I/O-bound.

Result:

- Multi-source latency reduced by about 60%.

### TTL Query Cache

Problem:

- Repeating the same question wasted LLM calls.

Options considered:

- Plain dict: rejected because it never expires.
- `functools.lru_cache`: rejected because instance methods include `self` in the cache key.
- Redis: rejected as overkill for a free portfolio demo.
- Disk cache: rejected due to file I/O and concurrency risk.
- TTL in-memory dict: chosen.

Decision criteria:

- Bounded memory.
- No dependency.
- No infrastructure.
- Auto-expiration.
- Fast repeat queries under 100ms.

### Progressive UI Disclosure

Problem:

- Users saw a spinner for 20-30 seconds and had no idea what was happening.

Options considered:

- LLM streaming: rejected because it streams final answer tokens, not agent progress.
- WebSocket/SSE: rejected as outside Streamlit's simple model.
- `st.empty()` placeholders plus progress callbacks: chosen.

Result:

- Users can see SQL, RAG, and Web completion times appear as each agent finishes.

### Auto-Scroll Improvements

Problem:

- After submitting a question, the user could remain scrolled at an old answer.
- Correction prompts could appear offscreen.
- Later, auto-scroll went to the end of the answer instead of the start.

Fixes:

- Added invisible anchors for the latest question and latest answer.
- Added two-phase scroll: first to question, then to answer start.
- Added retries for Streamlit render timing.

Decision criteria:

- The user should land at the beginning of the new answer, not the bottom.
- Streamlit DOM timing requires delayed retry logic.

## 8. Evals

You added an evaluation system because AI projects should prove behavior, not just claim it.

### Unit Tests

Purpose:

- Fast checks for validation, routing helpers, scoring, replay, and contracts.

Command:

```bash
python -m unittest discover -s tests -v
```

### Offline Evals

Purpose:

- Validate SQL/RAG/Web result contracts without calling LLMs or live services.

Command:

```bash
python -m evals.offline_eval
```

### Golden Evals

Purpose:

- Run real business questions through the real Fusion Agent.

They check:

- Route accuracy.
- Expected numbers.
- Confidence.
- Required evidence.
- Safety.
- Optional LLM-as-judge quality.

Important features:

- `--dry-run`.
- `--limit`.
- `--ids`.
- `--delay`.
- `--retries`.
- `--answer-only`.
- `--with-judge`.
- `--replay latest`.
- Trend tracking.

Decision criteria:

- Full evals can exhaust free-tier LLM quotas, so the runner needs pacing and replay.
- Rule-based scoring should remain primary; LLM-as-judge is optional.
- Expected numbers should be refreshable from the database.

## 9. Observability

After evals, the next question became: if an eval fails, where did it fail?

You added local JSON tracing:

- Trace ID.
- Question.
- Route.
- Routing model.
- SQL/RAG/Web spans.
- SQL query.
- Row count.
- RAG source summary.
- Web category and competitor count.
- Validation confidence.
- Final answer generation time.
- Slow spans.
- Error spans.
- Cache status.

Command:

```bash
python -m observability.inspect_traces --latest
```

Key design decision:

- Observability should not call extra LLMs. It records work the app already did.

Later security improvements:

- Redact API keys, tokens, secrets, passwords, PostgreSQL URLs, and OpenAI-style keys.
- Disable previews with `NEXUSIQ_TRACE_INCLUDE_PREVIEWS=0`.
- Limit retained trace files with `NEXUSIQ_TRACE_MAX_FILES`.
- Add trace schema versioning.

Decision criteria:

- Traces should help debugging without increasing quota usage.
- Trace files should be safe enough for local development.
- UI, CLI, and eval reports should share slow/error span logic to avoid drift.

## 10. Context Engineering

You found a real failure:

```text
Q4 Electronics revenue?
What about Q3?
```

The second question returned total Q3 revenue instead of Q3 Electronics revenue because the system was stateless.

### Conversation Memory

You added:

- Rolling history of the last 5 turns.
- Last 3 turns formatted into routing/fusion prompts.
- History saved after non-cached responses.

Decision criteria:

- Follow-up questions need prior business context.
- History should improve routing and final synthesis.
- It should stay bounded to avoid bloated prompts.

### Query Resolution

You found another failure:

```text
q1?
```

The raw query was too short for RAG and too ambiguous for SQL.

You added `_resolve_question()`:

- Uses conversation history.
- Rewrites short follow-ups into standalone business questions.
- Sends the resolved question to SQL/RAG/Web.
- Keeps the original question for cache keys, UI display, trace display, and history.

Decision criteria:

- RAG and SQL agents need complete queries.
- The user-facing conversation should still preserve the original wording.
- Query resolution is context engineering before retrieval, while memory is context engineering before answer generation.

## 11. Advanced RAG Improvements

You researched and addressed RAG failure modes:

- Missed top-ranked documents.
- Cross-document scatter.
- Metadata mismatch.
- Semantic compression loss.
- Query-document asymmetry.
- Chunk boundary issues.
- Lost-in-the-middle behavior.
- Short query failure.

Key fixes:

- Wire `hybrid_search()` into the simple query path instead of leaving it as dead code.
- Add adaptive HyDE for weak retrieval.
- Remove unsupported ChromaDB string `$contains` metadata filter.
- Use BM25 to naturally prioritize exact names, quarters, and numbers.

Decision criteria:

- Retrieval should be fixed at the retrieval layer, not hidden with prompt hacks.
- HyDE is useful but should be cost-aware.
- Simpler code with fewer unsupported filters is more reliable.

## 12. Dynamic Ingestion Pipeline

You moved the data layer closer to production by adding an ingestion CLI:

```bash
python -m database.ingestion_pipeline status
python -m database.ingestion_pipeline refresh-all --dry-run
python -m database.ingestion_pipeline rebuild-sql  # blocked: preserves Supabase SQL facts
python -m database.ingestion_pipeline rebuild-rag
python -m database.ingestion_pipeline add-pdf --path data/pdfs/01_financial/new_report.pdf --category 01_financial
python -m database.ingestion_pipeline clear-caches
```

Important features:

- SQL/RAG status inspection.
- Dry-run safety.
- Incremental PDF add/replace.
- Delete-then-upsert into ChromaDB.
- Ingestion version file.
- Lazy BM25 freshness refresh in running app.
- Tests for pipeline behavior.

Decision criteria:

- Adding one PDF should not require wiping the entire vector store.
- Upsert alone is not enough because edited PDFs can produce fewer chunks.
- A version file catches same-count edits that document count checks miss.
- BM25 should refresh lazily when needed, not require app restart.

## 13. Demo and Recruiter Experience

The project had strong backend depth, but the demo originally did not make that obvious enough.

You created a guided command center experience:

- KPI/status chips.
- Agent flow diagram.
- Featured answer preview.
- Prompt cards.
- Source badges.
- Guided demo buttons.
- Neutral "Guided Intelligence Command Center" wording.

The prompt cards cover:

- Q4 Electronics revenue validation.
- Q3 vs Q4 comparison.
- West vs South explanation.
- Competitor pricing.
- Return policy.
- October transaction count.

Decision criteria:

- Recruiters may not know what to ask.
- The strongest technical demo should be one click away.
- The page should show proof signals immediately: transactions, documents, agents, validation, live web.
- Avoid making the interface sound only like a "recruiter demo"; use neutral product language.

You also fixed:

- Command center re-entry for returning users.
- Prompt selection behavior.
- Sidebar prompt behavior.
- Two-phase scrolling.
- Featured answer numbers to match actual data.

## 14. Deployment Work

### Streamlit Keep-Alive

Problem:

- Streamlit free tier sleeps after inactivity.
- Recruiters may see a wake-up screen.

Research decisions:

- Render free tier rejected due to 512MB RAM limit.
- Oracle Cloud free tier rejected due to reliability/account termination risk.
- Hugging Face Spaces free tier rejected because it also hibernates.
- Vercel rejected because Streamlit needs persistent processes and WebSockets.
- Cloudflare Tunnel not pursued because it still needs an always-on machine.

Final solution:

- GitHub Actions plus Selenium headless Chrome.

Why:

- UptimeRobot HTTP pings do not create a real Streamlit WebSocket session.
- Selenium opens a real browser, creates a real session, and can click the wake button.

Important fixes:

- Use Ubuntu 22.04 because Ubuntu 24 Chromium snap causes CI issues.
- Check real Streamlit DOM, not just `readyState=interactive`.
- Increase post-wake verification to about 150 seconds because cold boot can take about 131 seconds.
- Add manual workflow dispatch and concurrency control.

### Cloud Run Scaffold

You later pushed a Cloud Run deployment scaffold to GitHub main:

- Dockerfile.
- `.dockerignore`.
- `docs/cloud-run.md`.

Decision criteria:

- Streamlit Cloud is useful for easy demos.
- Cloud Run gives a more production-style deployment path.
- Containerization improves reproducibility.

## 15. Files and Areas Touched

Important files and modules mentioned across the project history:

- `main.py`: Streamlit entry, home page, command center, launch behavior.
- `ui/fusion_chat.py`: Fusion UI, prompt cards, answer rendering, scroll behavior, observability panel.
- `ui/sql_chat.py`: SQL chat UI, history, exports, validation display.
- `agents/sql_agent.py`: natural language to SQL, fallback, validation, execution.
- `agents/rag_agent.py`: document retrieval, hybrid search, HyDE, BM25 refresh.
- `agents/web_agent.py`: scraping/API competitor intelligence.
- `agents/fusion_agent.py`: routing, orchestration, validation, caching, tracing, memory, query resolution.
- `utils/quota_tracker.py`: circuit breaker and provider availability state.
- `utils/validators.py`: typo/date/ambiguity validation.
- `config/settings.py`: model config and feature flags.
- `config/company_data.py`: guarded legacy synthetic rebuild fixture; Supabase is the runtime truth.
- `config/data_inventory.py`: source capabilities and inventory.
- `database/generate_aligned_data.py`: aligned SQL data generation.
- `database/generate_financial_pdfs.py`: SQL-driven financial PDF generation.
- `database/setup_rag_pipeline.py`: document indexing and ChromaDB setup.
- `database/ingestion_pipeline.py`: data refresh and incremental ingestion CLI.
- `evals/offline_eval.py`: deterministic source-contract evals.
- `evals/golden_eval.py`: live golden eval runner.
- `evals/golden_cases.json`: expected behavior dataset.
- `evals/judge.py`: optional LLM-as-judge scoring.
- `evals/refresh_golden_truth.py`: sync expected numbers with database truth.
- `observability/tracer.py`: local trace capture.
- `observability/inspect_traces.py`: trace reader and diagnostics.
- `docs/evaluation.md`: eval documentation.
- `docs/observability.md`: trace documentation.
- `docs/cloud-run.md`: Cloud Run deployment notes.

## 16. Decision Principles Used Throughout

Several consistent engineering principles show up across the project:

### 1. Prefer Source Validation Over Single-Source Trust

This is the core product idea. SQL gives precision, documents give context, web gives external intelligence, and Fusion compares them.

### 2. Fix the Root Layer

When vector search returned wrong chunks, you did not patch the prompt with hardcoded hints. You fixed retrieval with BM25 plus vector search.

### 3. Be Cost-Aware

Free-tier quotas shaped decisions:

- Circuit breaker for Gemini/Groq.
- HyDE only when retrieval confidence is weak.
- Golden eval delays, limits, retries, replay, and answer-only mode.
- No extra LLM calls for observability.

### 4. Avoid Overbuilding Infrastructure Too Early

Examples:

- TTL dict instead of Redis.
- ThreadPoolExecutor instead of full async rewrite.
- Local JSON traces instead of LangSmith/Langfuse/OpenTelemetry at first.
- Streamlit UI improvements instead of building a custom frontend.

### 5. Make the Demo Understandable

You repeatedly shifted from raw capability to guided experience:

- Prompt cards.
- Featured answer previews.
- Source badges.
- Command center.
- Observability panel.
- Clear confidence and validation.

### 6. Keep Data Aligned

Cross-source validation only works if SQL and documents are generated from the same truth. That led to `company_data.py`, aligned SQL generation, and SQL-driven PDF generation.

### 7. Make Failure Visible

You added:

- Model journey logs.
- Trace spans.
- Eval reports.
- Error spans.
- Slow span detection.
- Query history.
- Source routes.

This is what makes the system production-minded.

## 17. Strongest Interview Narrative

Use this version:

> NexusIQ AI is a multi-agent business intelligence system I built to solve the problem that business answers are unreliable when they come from only one source. When a user asks a question, NexusIQ routes it across SQL, document RAG, and live web agents, then uses a Fusion Agent to reconcile the outputs, compare numbers across sources, and return a confidence-scored answer with citations.
>
> The most important engineering work was not just making agents call LLMs. I had to solve real AI system problems: provider quota failures, bad vector retrieval, data mismatch between SQL and PDFs, slow multi-agent latency, ambiguous follow-up questions, stale vector indexes, and lack of visibility into failures. I added circuit breakers, BM25 plus vector hybrid search, source-of-truth data generation, parallel execution, TTL caching, conversation memory, query resolution, evals, and local observability traces.
>
> The result is a project that behaves more like a production AI intelligence system than a simple RAG chatbot.

## 18. Best Resume Bullets

Use these depending on role:

- Built a multi-source AI answer validation system that routes business questions across SQL, document RAG, and live web agents, then reconciles outputs with confidence scoring and source citations.
- Replaced vector-only retrieval with BM25 plus embedding hybrid search after diagnosing incorrect Q3/Q4 revenue retrieval, improving comparison-query accuracy on test prompts from 33% to 100%.
- Reduced multi-agent response latency by about 60% by running independent SQL, RAG, and Web agents concurrently with `ThreadPoolExecutor` and progressive UI status updates.
- Added circuit-breaker model fallback across Gemini and Groq to avoid quota retry spirals and reduce failed-query wait time by 30-60 seconds.
- Built cross-source validation logic that compares SQL exact values with document-extracted figures, producing confidence-scored answers for financial questions.
- Implemented eval infrastructure with unit tests, offline source-contract evals, live golden evals, optional LLM-as-judge scoring, replay, retry, delay, and trend tracking.
- Added local AI observability traces for route selection, SQL/RAG/Web spans, source summaries, validation confidence, slow steps, errors, and final answer generation.
- Built an incremental ingestion pipeline for structured sales data and unstructured business documents, safely refreshing ChromaDB vectors and BM25 indexes without full app restart.
- Added conversation memory and LLM-based query resolution so short follow-ups like `q1?` resolve into standalone business questions before SQL/RAG execution.
- Designed a guided command-center demo with validated sample prompts, source badges, agent flow, and evidence-first answer previews for recruiter-facing product clarity.

## 19. Criteria Behind Major Choices

| Choice | Criteria | Why It Was Chosen |
| --- | --- | --- |
| Gemini Flash primary | Free tier, speed, capability | Good default for fast LLM work |
| Groq fallback | Speed, free tier, provider diversity | Reduces dependency on one provider |
| Ollama/local option | Offline dev, no API quota | Useful fallback during quota exhaustion |
| ChromaDB | Local, free, simple | Fits portfolio scale and RAG use case |
| BM25 plus vector | Exact terms plus semantic meaning | Fixes quarter/date/number retrieval failures |
| Streamlit | Rapid AI app UI, easy deployment | Better than building React/FastAPI for this stage |
| ThreadPoolExecutor | I/O-bound agents, low refactor risk | Faster multi-agent queries without async rewrite |
| TTL cache | Bounded, simple, no infra | Avoids Redis/disk complexity |
| Local JSON traces | No extra services, no extra LLM calls | Enough observability for current stage |
| Selenium wake-up | Real WebSocket/browser session | HTTP pings do not keep Streamlit awake |
| Dry-run ingestion | Safety | Prevents accidental destructive data refresh |
| Delete-then-upsert PDFs | Correctness | Prevents stale chunks after edited PDFs shrink |

## 20. Current Project Identity

NexusIQ is best described as:

> A production-minded multi-agent AI intelligence system for business data, combining SQL analytics, document RAG, live web intelligence, cross-source validation, evals, observability, and guided product UX.

Avoid describing it only as:

- A chatbot.
- A Streamlit app.
- A RAG project.
- A SQL assistant.

Those are components. The main value is multi-source validation and trustworthy business answer generation.

## 21. Open Questions To Clarify

These are the only areas that may need your confirmation before using the report externally:

1. Should the final public story say "NexusIQ" only, or "NexusIQ AI" consistently?
2. Should the resume mention Supabase specifically, or keep it as PostgreSQL depending on the role?
3. Should the report include RevenueIQ as prior proof of real-data handling, or keep NexusIQ fully standalone?
4. Should the public demo emphasize Streamlit Cloud, Cloud Run, or both?
5. Should the recruiter-facing language say "business intelligence system" or "AI intelligence system"? The second sounds more modern; the first is clearer to traditional hiring managers.
6. Should any older Flask/FAISS baseline work be omitted from external storytelling to avoid confusing it with the current Streamlit/Fusion architecture?

## 22. Sources Used

- Notion: `#NPS2 Pro` parent page.
- Notion: `Complete Project Summary`.
- Notion: `Each Day Findings`.
- Notion: `Questions Raised`.
- Notion: `Code Files Execution Flow`.
- Notion: `Resume(Nexus)`.
- Notion: `Improvements made`.
- Notion: `Suggested Improvements (In Progress)`.
- Notion: `EVALS explained`.
- Notion: `Observability explained`.
- Project memory observations: 1411, 1412, 1414, 1415, 1416, 1417, 1418, 1419, 1433, 1434, 1435, 1520, 1524, 1543, 1546, 1811, 1821.
