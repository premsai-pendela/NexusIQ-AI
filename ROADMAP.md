# NexusIQ-AI Future Roadmap

Date: June 12, 2026 (supersedes June 10 version — several items shipped since)

Purpose: honest roadmap of what NexusIQ does NOT do yet. Everything here is
unbuilt or partial by design; everything already shipped lives in the Full
Report. Rule for inclusion: an item stays only if it strengthens trust,
accuracy, source coverage, reliability, cost efficiency, or enterprise
readiness. Demo theater and vanity features were removed.

## Shipped since the last version of this file (for context, not future work)

- LLM token/cost optimization: deterministic formatting for simple SQL,
  on-demand explanations, rules-based routing that skips the LLM router for
  obvious questions — measured 75% fewer model calls on simple SQL and 52%
  fewer tokens on SQL+RAG validation, proven with before/after ledger
  profiles; every skipped call logged with reason.
- Business-context layer (deterministic glossary retrieval injected into SQL
  generation): 2/10 → 10/10 on ambiguous business-metric evals, control
  questions byte-identical.
- Bounded verification loops: AST-validated SQL with one error-feedback
  repair pass; reranker-gated RAG evidence with retry and honest abstention.
- 194 tests + offline evals wired as a CI merge gate that fails the build on
  regression; 97.7% Hit@5 / 0.919 recall on a 43-query retrieval benchmark.
- Recruiter onboarding demo, trust guard, engineering post-mortems.

## Active Priorities

### Priority 1: Business-Context Auto-Learning

Today the glossary is hand-curated — perfect inside its scope, zero help
outside it, and every new metric costs a hand-written entry (the classic
semantic-layer breadth ceiling, measured firsthand via control evals).

Build:
- Schema scanner extracting tables, columns, relationships, sample values,
  and metric-like terms into candidate definitions.
- Mine query history and documents for definition evidence.
- Candidate definitions enter the glossary only through the existing eval
  gate — auto-discovered context must earn trust the same way hand-written
  context does.

Success metric: 50 unseen business questions; track SQL correctness, route
correctness, and token cost before/after. The interesting research question:
how to validate auto-discovered semantics before agents rely on them.

### Priority 2: Correction Feedback Loop

Cache is for speed; correction memory is for accuracy — different systems.

Flow: user marks an answer wrong with a reason ("revenue should exclude
refunds") → stored as scoped business context with source question,
timestamp, and confidence → future similar questions retrieve and apply it.
No fine-tuning; retrieval memory only. Admin review required before any
correction becomes company-wide. Corrections never apply blindly across
scopes.

### Priority 3: Semantic Cross-Source Validation Precision

Current validator can compare numerically-close but semantically-unrelated
facts, producing false LOW confidence on broad fusion answers.

Build: match facts by semantic label (revenue vs revenue, return rate vs
return rate) before numeric comparison; ignore unrelated support metrics
unless asked. Tests: broad query must not go LOW from unrelated numbers;
true revenue mismatch must still go LOW; rounded PDF figure must match exact
SQL figure.

### Priority 4: Company Onboarding & Tenant Isolation

Move from demo-company BI to company-onboardable product: workspace model,
database connection manager, document upload with ingestion queue, source
registry (ID, type, version hash, ingestion/indexing status, chunk count,
error), indexing status dashboard, role-based access, secrets handling, and
strict per-tenant isolation of data, context memory, and traces.

### Priority 5: Multi-Format Ingestion

PDF ingestion with incremental sync exists. Add: CSV, Excel, Word,
scanned-PDF/screenshot OCR, and static web-page indexing. Design rule:
structured sources (CSV/Excel) may become SQL-queryable tables or RAG
evidence depending on content — the registry records which, and every
source keeps a citation path. SQL data and RAG documents stay distinct.

### Priority 6: Observability Durability

Local JSONL traces + LLM ledger + Langfuse export exist but do not survive
container redeploys. Decide primary production trace store (Langfuse vs
S3-shipped JSONL), then add alerts: slow queries, high fallback rate,
invalid structured output, token-budget breach, provider quota exhaustion,
Chroma chunk-count drop.

### Priority 7: Retrieval at Scale (Hierarchical)

For corpora beyond a few thousand documents: route to source group →
retrieve candidate documents → retrieve chunks → rerank → merge evidence in
order, with map-reduce summarization for very large analyses. Prerequisite:
collection-level routing and source clustering in the registry.

### Priority 8: Route Self-Check

Rules-based routing for obvious questions shipped (part of the token work).
Remaining: route-confidence scoring with clarification fallback — a
low-confidence route decision should ask the user rather than run the wrong
path — plus golden evals dedicated to route correctness.

## Platform Maturity (later, kept lean)

- Terraform/IaC for the AWS deployment.
- Vector-store adapter (Chroma ↔ Qdrant/pgvector) to remove DB lock-in.
- Token budgets per query type with graceful over-budget fallback.
- Load testing with published latency percentiles.
- Optional dbt metrics layer when the data-platform story needs it.

## Removed from the roadmap (deliberately)

Visitor analytics, demo confidence variety, extra LLM provider backups
without eval coverage, and standalone user personalization — none of them
strengthen trust, accuracy, reliability, cost, or enterprise readiness for
this system. Personalization survives only as correction memory and
workspace context inside Priorities 2 and 4.

## Rule for All Future Work

Every improvement must strengthen at least one of: trust, accuracy, source
coverage, reliability, cost efficiency, enterprise readiness. New context
(auto-learned, corrected, or ingested) enters the system only through eval
gates — the same bar hand-written context passes today.
