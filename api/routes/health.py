import time
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.models.schemas import HealthResponse
from agents._singleton import get_fusion_agent, get_sql_agent, get_rag_agent, get_web_agent

router = APIRouter()

_START_TIME = time.time()


def _chroma_chunk_count() -> int:
    try:
        return get_rag_agent().collection.count()
    except Exception:
        return -1


def _cache_entry_count() -> int:
    try:
        return len(get_fusion_agent()._query_cache)
    except Exception:
        return -1


@router.get("/health", response_model=HealthResponse)
async def health():
    agents_status = {}
    degraded = False

    # DB check
    try:
        agent = get_sql_agent()
        agent.session.execute(text("SELECT 1"))
        agents_status["sql"] = "online"
    except Exception as e:
        agents_status["sql"] = f"degraded: {str(e)[:60]}"
        degraded = True

    # RAG / ChromaDB check
    try:
        count = get_rag_agent().collection.count()
        agents_status["rag"] = "online"
    except Exception as e:
        agents_status["rag"] = f"degraded: {str(e)[:60]}"
        degraded = True
        count = -1

    # Web agent check (lightweight)
    try:
        _ = get_web_agent()
        agents_status["web"] = "online"
    except Exception as e:
        agents_status["web"] = f"degraded: {str(e)[:60]}"

    # Fusion
    try:
        _ = get_fusion_agent()
        agents_status["fusion"] = "online"
    except Exception as e:
        agents_status["fusion"] = f"degraded: {str(e)[:60]}"
        degraded = True

    chroma_chunks = _chroma_chunk_count()
    cache_entries = _cache_entry_count()
    status = "degraded" if degraded else "healthy"
    response = HealthResponse(
        status=status,
        agents=agents_status,
        chroma_chunks=chroma_chunks,
        cache_entries=cache_entries,
        uptime_seconds=round(time.time() - _START_TIME, 1),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    http_status = 503 if degraded else 200
    return JSONResponse(content=response.model_dump(), status_code=http_status)


@router.get("/agents/status")
async def agents_status():
    status = {}
    for name, getter in [("sql", get_sql_agent), ("rag", get_rag_agent),
                          ("web", get_web_agent), ("fusion", get_fusion_agent)]:
        try:
            getter()
            status[name] = {"status": "online"}
        except Exception as e:
            status[name] = {"status": "degraded", "error": str(e)[:80]}
    return status


@router.get("/metrics")
async def metrics():
    try:
        quota_status = get_sql_agent().tracker.get_status_report()
    except Exception:
        quota_status = {}
    return {
        "queries_in_cache": _cache_entry_count(),
        "quota_status": quota_status,
        "chroma_chunk_count": _chroma_chunk_count(),
        "server_uptime_seconds": round(time.time() - _START_TIME, 1),
    }
