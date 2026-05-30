import asyncio
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException

from api.models.schemas import QueryRequest, QueryResponse, SourceCitation
from api.middleware.auth import verify_api_key
from agents._singleton import get_sql_agent, get_rag_agent

router = APIRouter()

_TIMEOUT = 30


def _map_rag_sources(chunks: list) -> list[SourceCitation]:
    sources = []
    for chunk in chunks or []:
        sources.append(SourceCitation(
            type="rag",
            content=str(chunk.get("content", chunk.get("document", "")))[:500],
            filename=chunk.get("filename") or chunk.get("source"),
        ))
    return sources


@router.post("/sql", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
async def query_sql(req: QueryRequest):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, get_sql_agent().ask, req.question),
            timeout=_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="SQL agent timed out")
    latency_ms = (time.time() - start) * 1000
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "SQL agent error"))
    return QueryResponse(
        answer=result.get("answer", ""),
        confidence="HIGH" if result.get("success") else "LOW",
        route="sql_only",
        sources=[],
        latency_ms=latency_ms,
        cached=False,
        request_id=request_id,
    )


@router.post("/rag", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
async def query_rag(req: QueryRequest):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, get_rag_agent().query, req.question),
            timeout=_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="RAG agent timed out")
    latency_ms = (time.time() - start) * 1000
    sources = _map_rag_sources(result.get("sources", []))
    return QueryResponse(
        answer=result.get("answer", ""),
        confidence="HIGH" if result.get("chunks_retrieved", 0) > 0 else "LOW",
        route="rag_only",
        sources=sources,
        latency_ms=latency_ms,
        cached=False,
        request_id=request_id,
    )
