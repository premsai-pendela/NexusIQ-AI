"""
Automated test runner for NexusIQ-AI Fusion Agent.
Reads test_queries.txt, runs every query, captures routing/errors/timing,
writes a structured JSON + Markdown report.

Usage:
    python run_tests.py                      # run all 105 queries
    python run_tests.py --phase 1            # phase 1 only (queries #1,16,31,46,26)
    python run_tests.py --section "SQL ONLY" # one section
    python run_tests.py --ids 1,16,31        # specific query IDs
    python run_tests.py --dry-run            # print queries without running
"""

import sys
import json
import time
import traceback
import argparse
from datetime import datetime
from pathlib import Path

# ── Per-query routing overrides ──────────────────────────────────────────────
# Use when LLM routing is smarter than the section-level expectation.
# Key: query ID, Value: (expected_routing, reason)
ROUTING_OVERRIDES = {
    1:  ("sql_rag",  "LLM cross-validates total revenue against PDF reports — correct behavior"),
    26: ("sql_rag",  "'All metrics' includes SQL transaction data; pure rag_only is too narrow"),
}

# ── Phase presets ────────────────────────────────────────────────────────────
PHASES = {
    1: {"name": "Basic Functionality", "ids": [1, 16, 31, 46, 26]},
    2: {"name": "Cross-Validation",    "ids": [46, 51, 85]},
    3: {"name": "Edge Cases",          "ids": [91, 92, 93, 94, 95]},
    4: {"name": "Advanced Features",   "ids": [26, 27, 99, 85, 86, 87]},
    5: {"name": "Chart Builder",       "ids": [7, 10, 6, 15]},
}

# ── Expected routing per section ─────────────────────────────────────────────
SECTION_ROUTING = {
    "SQL ONLY":              "sql_only",
    "RAG ONLY":              "rag_only",
    "WEB ONLY":              "web_only",
    "SQL + RAG FUSION":      "sql_rag",   # any variant containing both
    "SQL + WEB FUSION":      "sql_web",
    "RAG + WEB FUSION":      "rag_web",
    "ALL SOURCES FUSION":    "all",
    "EDGE CASES":            None,        # no single expected route
}

# ── Routing match helper ──────────────────────────────────────────────────────
def routing_matches(actual: str, expected: str) -> bool:
    if expected is None:
        return True  # edge cases: no expectation
    actual = actual.lower()
    expected = expected.lower()
    if actual == expected:
        return True
    # Flexible: sql_rag == rag_sql == both == "sql_rag"
    if expected == "sql_rag":
        return ("sql" in actual and "rag" in actual) or actual in ("both", "rag_sql", "sql_rag")
    if expected == "sql_web":
        return "sql" in actual and "web" in actual
    if expected == "rag_web":
        return "rag" in actual and "web" in actual
    if expected == "all":
        return "sql" in actual and "rag" in actual and "web" in actual
    return False


# ── Parse test_queries.txt ────────────────────────────────────────────────────
def parse_queries(path: Path) -> list[dict]:
    """
    Returns list of dicts:
      { id, text, section, difficulty, expected_routing }
    """
    queries = []
    current_section = None
    current_difficulty = None

    section_map = {}  # map header keywords → SECTION_ROUTING keys
    for key in SECTION_ROUTING:
        section_map[key.upper()] = key

    lines = path.read_text().splitlines()
    i = 0
    in_query_block = False   # True only inside a ``` code block
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        # Stop at non-query sections
        if "RECOMMENDED TESTING ORDER" in line.upper() or "SUCCESS CRITERIA" in line.upper() or "KNOWN ISSUES" in line.upper() or "EXPECTED RESULTS" in line.upper():
            break

        # Track ``` code blocks — only parse numbered lines inside them
        if line.startswith("```"):
            in_query_block = not in_query_block
            continue

        # Section headers  ## 1️⃣ SQL ONLY QUERIES
        if line.startswith("## "):
            upper = line.upper()
            for key_upper, key in section_map.items():
                if key_upper in upper:
                    current_section = key
                    break

        # Difficulty headers  ### **Simple**
        elif line.startswith("### "):
            text = line.replace("#", "").replace("*", "").strip().upper()
            if "SIMPLE" in text:
                current_difficulty = "simple"
            elif "MEDIUM" in text:
                current_difficulty = "medium"
            elif "ADVANCED" in text:
                current_difficulty = "advanced"
            elif "VALIDATION" in text:
                current_difficulty = "validation"
            elif "COMPARISON" in text:
                current_difficulty = "comparison"
            elif "CATEGORY" in text:
                current_difficulty = "category"

        # Numbered queries  1. What is the total revenue?  (only inside ``` blocks)
        elif current_section and in_query_block and line and line[0].isdigit():
            # strip markdown list chars like ``` block markers
            clean = line.strip("`").strip()
            dot = clean.find(".")
            if dot > 0:
                try:
                    qid = int(clean[:dot])
                except ValueError:
                    continue
                text = clean[dot + 1:].strip()
                # strip inline comment after  (
                comment = None
                if "  (" in text:
                    text, comment = text.split("  (", 1)
                    comment = comment.rstrip(")")

                queries.append({
                    "id": qid,
                    "text": text,
                    "section": current_section,
                    "difficulty": current_difficulty,
                    "expected_routing": SECTION_ROUTING.get(current_section),
                    "note": comment,
                })

    # Apply per-query overrides
    for q in queries:
        if q["id"] in ROUTING_OVERRIDES:
            override_route, reason = ROUTING_OVERRIDES[q["id"]]
            q["expected_routing"] = override_route
            q["override_reason"] = reason

    queries.sort(key=lambda q: q["id"])
    return queries


# ── Run a single query ────────────────────────────────────────────────────────
def run_query(agent, q: dict) -> dict:
    result = {
        "id": q["id"],
        "text": q["text"],
        "section": q["section"],
        "difficulty": q["difficulty"],
        "expected_routing": q["expected_routing"],
        "note": q.get("note"),
        "status": None,         # pass / routing_mismatch / error
        "actual_routing": None,
        "routing_match": None,
        "answer_snippet": None,
        "validation_confidence": None,
        "query_time_s": None,
        "error": None,
        "error_traceback": None,
    }

    t0 = time.time()
    try:
        resp = agent.query(q["text"])
        elapsed = time.time() - t0

        actual = resp.get("source_type", "unknown")
        match = routing_matches(actual, q["expected_routing"])
        answer = resp.get("answer", "") or ""
        snippet = answer[:200].replace("\n", " ") + ("…" if len(answer) > 200 else "")

        val_conf = None
        if resp.get("validation"):
            val_conf = resp["validation"].get("confidence")

        result.update({
            "status": "pass" if match else "routing_mismatch",
            "actual_routing": actual,
            "routing_match": match,
            "answer_snippet": snippet,
            "validation_confidence": val_conf,
            "query_time_s": round(elapsed, 2),
        })

    except Exception as exc:
        elapsed = time.time() - t0
        result.update({
            "status": "error",
            "error": str(exc),
            "error_traceback": traceback.format_exc(),
            "query_time_s": round(elapsed, 2),
        })

    return result


# ── Build Markdown report ─────────────────────────────────────────────────────
def build_report(results: list[dict], meta: dict) -> str:
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    mismatched = sum(1 for r in results if r["status"] == "routing_mismatch")
    errors = sum(1 for r in results if r["status"] == "error")
    avg_time = sum(r["query_time_s"] or 0 for r in results) / max(total, 1)

    lines = [
        "# NexusIQ-AI Test Report",
        f"**Date:** {meta['date']}  ",
        f"**Duration:** {meta['duration_s']:.1f}s  ",
        f"**Queries:** {total}  ",
        "",
        "## Summary",
        f"| Status | Count | % |",
        f"|--------|-------|---|",
        f"| ✅ Pass | {passed} | {passed*100//total}% |",
        f"| ⚠️ Routing mismatch | {mismatched} | {mismatched*100//total}% |",
        f"| ❌ Error | {errors} | {errors*100//total}% |",
        f"| Avg response time | {avg_time:.1f}s | — |",
        "",
    ]

    # Group by section
    sections = {}
    for r in results:
        sections.setdefault(r["section"], []).append(r)

    for section, rows in sections.items():
        sec_pass = sum(1 for r in rows if r["status"] == "pass")
        lines.append(f"## {section}  ({sec_pass}/{len(rows)} pass)")
        lines.append("")
        lines.append("| # | Difficulty | Expected | Actual | Status | Time | Answer |")
        lines.append("|---|-----------|----------|--------|--------|------|--------|")
        for r in rows:
            status_icon = {"pass": "✅", "routing_mismatch": "⚠️", "error": "❌"}.get(r["status"], "?")
            expected = r["expected_routing"] or "varies"
            actual = r["actual_routing"] or r["error"] or "—"
            snippet = (r["answer_snippet"] or r["error"] or "—")[:80]
            time_s = f"{r['query_time_s']}s" if r["query_time_s"] else "—"
            lines.append(
                f"| {r['id']} | {r['difficulty']} | `{expected}` | `{actual}` "
                f"| {status_icon} | {time_s} | {snippet} |"
            )
        lines.append("")

    # Errors section
    error_results = [r for r in results if r["status"] == "error"]
    if error_results:
        lines.append("## Errors (full detail)")
        lines.append("")
        for r in error_results:
            lines.append(f"### #{r['id']} — {r['text']}")
            lines.append(f"```\n{r['error_traceback']}\n```")
            lines.append("")

    # Routing mismatches section
    mismatch_results = [r for r in results if r["status"] == "routing_mismatch"]
    if mismatch_results:
        lines.append("## Routing Mismatches")
        lines.append("")
        for r in mismatch_results:
            lines.append(f"- **#{r['id']}** `{r['text'][:60]}`")
            lines.append(f"  - Expected: `{r['expected_routing']}` | Got: `{r['actual_routing']}`")
        lines.append("")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="NexusIQ-AI automated test runner")
    parser.add_argument("--phase",   type=int,   help="Run a preset phase (1-5)")
    parser.add_argument("--section", type=str,   help="Run one section (e.g. 'SQL ONLY')")
    parser.add_argument("--ids",     type=str,   help="Comma-separated query IDs (e.g. 1,16,31)")
    parser.add_argument("--dry-run", action="store_true", help="Print queries, don't run")
    parser.add_argument("--output",  type=str,   default=".gstack/test-reports", help="Output directory")
    args = parser.parse_args()

    root = Path(__file__).parent
    queries_file = root / "test_queries.txt"

    print(f"Parsing {queries_file}…")
    all_queries = parse_queries(queries_file)
    print(f"  Found {len(all_queries)} queries")

    # Filter
    selected = all_queries
    if args.phase:
        phase = PHASES.get(args.phase)
        if not phase:
            print(f"Unknown phase {args.phase}. Valid: {list(PHASES.keys())}")
            sys.exit(1)
        ids = set(phase["ids"])
        selected = [q for q in all_queries if q["id"] in ids]
        print(f"  Phase {args.phase} ({phase['name']}): {len(selected)} queries")
    elif args.ids:
        ids = set(int(x.strip()) for x in args.ids.split(","))
        selected = [q for q in all_queries if q["id"] in ids]
        print(f"  Filtered to IDs {args.ids}: {len(selected)} queries")
    elif args.section:
        selected = [q for q in all_queries if args.section.upper() in q["section"].upper()]
        print(f"  Section '{args.section}': {len(selected)} queries")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for q in selected:
            print(f"  #{q['id']:3d} [{q['section']} / {q['difficulty']}]  {q['text']}")
        return

    # Import agent (lazy — only on real run)
    print("\nLoading Fusion Agent…")
    sys.path.insert(0, str(root))
    from agents.fusion_agent import get_fusion_agent
    agent = get_fusion_agent()

    # Run
    out_dir = root / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    t_start = time.time()
    total = len(selected)

    print(f"\nRunning {total} queries…\n")
    for i, q in enumerate(selected, 1):
        tag = f"#{q['id']:3d} [{q['section'][:20]} / {q['difficulty']}]"
        print(f"  [{i:3d}/{total}] {tag}  {q['text'][:55]}…", end=" ", flush=True)
        r = run_query(agent, q)
        icon = {"pass": "✅", "routing_mismatch": "⚠️", "error": "❌"}.get(r["status"], "?")
        print(f"{icon}  {r['actual_routing'] or r['error'] or '—'}  ({r['query_time_s']}s)")
        results.append(r)

    duration = time.time() - t_start

    # Write outputs
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    json_path = out_dir / f"test-results-{ts}.json"
    md_path   = out_dir / f"test-report-{ts}.md"

    meta = {"date": ts, "duration_s": duration}
    json_path.write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    md_path.write_text(build_report(results, meta))

    # Console summary
    passed    = sum(1 for r in results if r["status"] == "pass")
    mismatched = sum(1 for r in results if r["status"] == "routing_mismatch")
    errors    = sum(1 for r in results if r["status"] == "error")

    print(f"\n{'─'*60}")
    print(f"  ✅ Pass:             {passed}/{total}")
    print(f"  ⚠️  Routing mismatch: {mismatched}/{total}")
    print(f"  ❌ Error:            {errors}/{total}")
    print(f"  ⏱  Total time:       {duration:.1f}s")
    print(f"{'─'*60}")
    print(f"  Report: {md_path}")
    print(f"  JSON:   {json_path}")

    if errors:
        print(f"\n  ❌ ERRORS:")
        for r in results:
            if r["status"] == "error":
                print(f"    #{r['id']} {r['text'][:55]} — {r['error']}")

    if mismatched:
        print(f"\n  ⚠️  ROUTING MISMATCHES:")
        for r in results:
            if r["status"] == "routing_mismatch":
                print(f"    #{r['id']} expected={r['expected_routing']} got={r['actual_routing']}")

    agent.close()


if __name__ == "__main__":
    main()
