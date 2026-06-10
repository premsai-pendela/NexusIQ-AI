"""Company onboarding walkthrough (demo mode).

Shows the NexusIQ product vision end to end: connect a company database and
document corpus, let the system learn the schema and business definitions,
then ask a question and get a validated, traced, cost-accounted answer.

DEMO MODE boundary (honest): this runs against the single demo workspace
(sample Supabase database + bundled document corpus). There is no user
registration, tenant isolation, or customer secret storage — what real
onboarding requires is documented in docs/DEMO.md.

Usage:
    python -m scripts.onboarding_demo                 # schema + docs + glossary steps
    python -m scripts.onboarding_demo --ask "What was net revenue in Q4 2024?"
    python -m scripts.onboarding_demo --offline       # skip DB/LLM network steps
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))


def mask_database_url(url: str) -> str:
    """Hide credentials and host details; keep scheme and database name."""
    if not url:
        return "(not configured)"
    masked = re.sub(r"//[^@/]+@", "//***:***@", url)
    masked = re.sub(r"@[^/]+/", "@***/", masked)
    return masked


def summarize_glossary(entries) -> dict:
    """Compact summary of the business glossary for display."""
    by_category = {}
    for entry in entries:
        by_category.setdefault(entry.category, []).append(entry.id)
    return {
        "entries": len(entries),
        "by_category": {category: sorted(ids) for category, ids in sorted(by_category.items())},
    }


def banner(text: str) -> None:
    print(f"\n{'=' * 64}\n{text}\n{'=' * 64}")


def step_connect_database(offline: bool) -> None:
    banner("STEP 1 — Connect company database")
    from config.settings import settings

    print(f"Connection: {mask_database_url(settings.database_url)}")
    if offline:
        print("(offline mode: skipping live schema scan)")
        return

    from sqlalchemy import create_engine, text

    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT table_name, COUNT(*) AS columns "
            "FROM information_schema.columns WHERE table_schema = 'public' "
            "GROUP BY table_name ORDER BY table_name"
        )).fetchall()
        print(f"Schema scan: {len(rows)} tables discovered")
        for table, column_count in rows:
            try:
                row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
            except Exception:
                row_count = "?"
            print(f"  - {table}: {column_count} columns, {row_count:,} rows" if isinstance(row_count, int)
                  else f"  - {table}: {column_count} columns")
    print("This same scan feeds the SQL agent's schema context at query time.")


def step_document_corpus(offline: bool) -> None:
    banner("STEP 2 — Connect document corpus")
    pdf_dir = Path("data/pdfs")
    pdf_count = len(list(pdf_dir.rglob("*.pdf"))) if pdf_dir.exists() else 0
    print(f"Documents: {pdf_count} PDFs under {pdf_dir}/")
    if offline:
        print("(offline mode: skipping vector index count)")
        return
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        from config.settings import settings

        # Must match RAGAgent's client settings — chromadb refuses a second
        # client on the same path with different settings.
        client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        collections = {c.name: c.count() for c in client.list_collections()}
        for name, count in sorted(collections.items()):
            print(f"  - Chroma collection '{name}': {count} indexed chunks")
    except Exception as exc:
        print(f"  (Chroma inspection unavailable: {exc})")
    print("Retrieval over this corpus is hybrid: BM25 + embeddings + reranker.")


def step_business_context() -> None:
    banner("STEP 3 — Learn business definitions")
    from context.business_context import build_context_block, load_glossary

    entries = load_glossary()
    summary = summarize_glossary(entries)
    print(f"Business glossary: {summary['entries']} company-specific definitions")
    for category, ids in summary["by_category"].items():
        print(f"  - {category}: {', '.join(ids)}")

    sample = "What was net revenue in Q4 2024?"
    retrieved = build_context_block(sample)
    print(f"\nExample retrieval for: \"{sample}\"")
    print(f"  definitions applied: {retrieved['ids'] or 'none'} ({retrieved['chars']} prompt chars)")
    print("Only relevant definitions are injected into SQL generation — measured")
    print("2/10 -> 10/10 on ambiguous business questions (docs/business_context_layer.md).")


def step_ask(question: str) -> None:
    banner(f"STEP 4 — Ask: {question}")
    from agents._singleton import get_fusion_agent

    agent = get_fusion_agent()
    result = agent.query(question, bypass_cache=True)

    validation = result.get("validation") or {}
    sql_result = result.get("sql_result") or {}
    usage = result.get("llm_usage") or {}

    print(f"\nAnswer:\n{result.get('answer', '')[:600]}\n")
    print(f"Route: {result.get('source_type')}")
    print(f"Validation confidence: {validation.get('confidence', 'n/a')}")
    print(f"Answer generation: {result.get('answer_generation_mode')}")
    print(f"Business context applied: {(sql_result.get('business_context') or {}).get('ids', [])}")
    print(f"LLM calls: {usage.get('successful_calls', 0)} successful, "
          f"{usage.get('avoided_calls', 0)} avoided "
          f"({usage.get('avoided_estimated_tokens', 0)} prompt tokens not sent)")
    print(f"Estimated tokens: {usage.get('successful_estimated_tokens', 0)} | "
          f"Actual provider tokens: {usage.get('actual_tokens', 0)}")
    print(f"Trace ID: {result.get('trace_id')} (full span tree in traces/)")


def main() -> int:
    parser = argparse.ArgumentParser(description="NexusIQ company onboarding walkthrough (demo mode)")
    parser.add_argument("--ask", type=str, default=None, help="Run a real question through the full pipeline")
    parser.add_argument("--offline", action="store_true", help="Skip steps that need database/LLM access")
    parser.add_argument("--json", action="store_true", help="Print glossary summary as JSON and exit")
    args = parser.parse_args()

    if args.json:
        from context.business_context import load_glossary
        print(json.dumps(summarize_glossary(load_glossary()), indent=2))
        return 0

    banner("NexusIQ — Company Data Onboarding (DEMO MODE)")
    print("Single demo workspace. No auth, tenancy, or customer secret storage —")
    print("production onboarding requirements: docs/DEMO.md section 'What real")
    print("onboarding adds'.")

    step_connect_database(args.offline)
    step_document_corpus(args.offline)
    step_business_context()

    if args.ask and not args.offline:
        step_ask(args.ask)
    elif args.ask:
        print("\n(--ask skipped in offline mode)")
    else:
        banner("STEP 4 — Ask a question (optional)")
        print("Re-run with: python -m scripts.onboarding_demo --ask \"What was net revenue in Q4 2024?\"")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
