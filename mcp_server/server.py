import asyncio
import json
import logging
import os

from fastmcp import FastMCP

from agents._singleton import (
    get_fusion_agent,
    get_sql_agent,
    get_rag_agent,
    get_web_agent,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "NexusIQ Business Intelligence",
    instructions=(
        "You have access to a production business intelligence system containing: "
        "100,000 sales transactions (FY2024, $175M revenue), "
        "43 business PDF documents (financial reports, contracts, strategy docs), "
        "and live competitor pricing data. "
        "Use query_business_intelligence for complex questions. "
        "Use query_database for exact figures. "
        "Use search_business_documents for policies and context."
    ),
)


@mcp.tool()
async def query_business_intelligence(question: str, timeout_seconds: int = 25) -> str:
    """Use ONLY for questions that require BOTH database numbers AND document context together,
    OR questions about strategy, trends, or explanations that need cross-source validation.
    Examples: 'Why did East region underperform?', 'Validate Q4 revenue against financial reports'.
    Do NOT use for simple ranking, totals, or comparisons — use query_database for those (it's 10x faster).
    Returns validated answer with confidence level and source citations."""
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: get_fusion_agent().query(question)),
            timeout=timeout_seconds,
        )
        confidence = (result.get("validation") or {}).get("confidence") or "UNKNOWN"
        answer = result.get("answer", "No answer generated")
        route = result.get("source_type", "unknown")
        return f"[{confidence} confidence | route: {route}]\n\n{answer}"
    except asyncio.TimeoutError:
        return (
            f"Query timed out after {timeout_seconds}s. "
            "Try query_database for a direct SQL question instead."
        )
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def query_database(question: str) -> str:
    """FASTEST tool — use this first for any question answerable from sales data alone.
    Covers: revenue totals, regional rankings, top/bottom performers, category breakdowns,
    monthly/quarterly trends, transaction counts, averages, comparisons between regions or products.
    FY2024 data: 5 regions (East/West/North/South/Central), 5 product categories, $175M total revenue, 100K transactions.
    Returns exact figures and the SQL used. Responds in 3-5 seconds."""
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, get_sql_agent().ask, question),
            timeout=20,
        )
        if not result.get("success"):
            return f"SQL error: {result.get('error', 'unknown')}"
        answer = result.get("answer", "")
        sql = result.get("query", "")
        return f"{answer}\n\nSQL: {sql}" if sql else answer
    except asyncio.TimeoutError:
        return "SQL query timed out. Try a more specific question."
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def search_business_documents(query: str, n_results: int = 5) -> str:
    """Search 43 business PDFs: Q1-Q4 2024 financial reports, market
    analysis, supplier contracts, operations SOPs, HR policies,
    strategic plans. Returns document-only excerpts with source citations
    and retrieval scores. Does not query SQL or validate database totals."""
    loop = asyncio.get_event_loop()
    try:
        chunks = await asyncio.wait_for(
            loop.run_in_executor(None, get_rag_agent().hybrid_search, query, n_results),
            timeout=15,
        )
        if not chunks:
            return "No relevant documents found."
        return _format_document_chunks(chunks)
    except asyncio.TimeoutError:
        return "Document search timed out."
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_competitor_pricing(category: str) -> str:
    """Get live competitor product pricing.
    Valid categories: electronics, home, clothing, food, sports.
    Returns current prices from partner retail sources with timestamp."""
    valid = {"electronics", "home", "clothing", "food", "sports"}
    if category.lower() not in valid:
        return f"Invalid category. Choose from: {', '.join(sorted(valid))}"
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: get_web_agent().query(
                    f"What are competitor prices for {category}?",
                    category=category.lower(),
                ),
            ),
            timeout=20,
        )
        if not result.get("success"):
            return f"Web agent error: {result.get('error', 'unknown')}"
        return result.get("answer", str(result))
    except asyncio.TimeoutError:
        return "Web scraping timed out. Try again in a few seconds."
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.resource("nexusiq://schema")
async def get_schema() -> str:
    """Database schema for NexusIQ sales_transactions table."""
    return get_sql_agent()._get_schema_info()


@mcp.resource("nexusiq://status")
async def get_status() -> str:
    """Current NexusIQ system status and data inventory."""
    try:
        chunk_count = get_rag_agent().collection.count()
    except Exception:
        chunk_count = 425  # fallback

    return json.dumps(_build_status_payload(chunk_count), indent=2)


def _format_document_chunks(chunks: list) -> str:
    results = [
        "Document search results only. These excerpts come from PDFs, not the SQL database. "
        "Use query_database or query_business_intelligence for SQL validation.",
        "Scores: rerank is the final cross-encoder relevance score when available; "
        "hybrid is the first-pass BM25/vector score.",
    ]
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("filename", "unknown")
        content = str(chunk.get("text", chunk.get("content", chunk.get("document", ""))))[:300]
        rerank_score = chunk.get("rerank_score")
        hybrid_score = chunk.get("similarity")
        if rerank_score is not None:
            score_text = f"rerank: {float(rerank_score):.3f}, hybrid: {float(hybrid_score or 0):.3f}"
        else:
            score_text = f"hybrid: {float(hybrid_score or 0):.3f}"
        results.append(f"{i}. [{source}] ({score_text})\n{content}")
    return "\n\n".join(results)


def _build_status_payload(chunk_count: int) -> dict:
    return {
        "system": "NexusIQ Business Intelligence",
        "sql_rows": 100000,
        "pdf_documents": 43,
        "chroma_chunks": chunk_count,
        "web_categories": ["electronics", "home", "clothing", "food", "sports"],
        "data_period": "FY2024",
        "total_revenue_analyzed": "$175,595,178.16",
    }


@mcp.prompt()
def business_analyst_query(
    topic: str,
    time_period: str = "2024",
    metric: str = "revenue",
) -> str:
    """Structured prompt template for business intelligence queries."""
    return (
        f"Analyze {metric} for {topic} during {time_period}. "
        "Include: 1) exact figures from the database, "
        "2) context from business documents, "
        "3) comparison to benchmarks if available, "
        "4) key insights and anomalies, "
        "5) recommended actions."
    )


def _warmup():
    try:
        get_fusion_agent()
        logger.info("MCP Server: agents pre-warmed")
    except Exception as e:
        logger.warning("MCP Server: warmup warning: %s", e)


if os.getenv("NEXUSIQ_MCP_PREWARM", "0").lower() in {"1", "true", "yes"}:
    _warmup()

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse", host="0.0.0.0", port=8002)
    else:
        mcp.run(transport="stdio")
