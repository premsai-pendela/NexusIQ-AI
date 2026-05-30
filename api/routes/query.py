import asyncio
import json
import queue
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.models.schemas import QueryRequest, QueryResponse, SourceCitation
from api.middleware.auth import verify_api_key
from agents._singleton import get_fusion_agent

router = APIRouter()

_TIMEOUT = 60


def _map_sources(raw_sources: list) -> list[SourceCitation]:
    out = []
    for s in raw_sources or []:
        if isinstance(s, dict):
            out.append(SourceCitation(
                type=s.get("type", "rag"),
                content=str(s.get("content", s.get("document", "")))[:500],
                filename=s.get("filename") or s.get("source"),
            ))
    return out


def _confidence_from_result(result: dict) -> str:
    validation = result.get("validation") or {}
    return validation.get("confidence") or "UNKNOWN"


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
async def query(req: QueryRequest):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    loop = asyncio.get_event_loop()

    force_map = {"auto": None, "sql": "sql_only", "rag": "rag_only",
                 "web": "web_only", "all": "all"}
    force_source = force_map.get(req.source)

    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: get_fusion_agent().query(req.question, force_source=force_source),
            ),
            timeout=_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Query timed out")

    latency_ms = (time.time() - start) * 1000
    return QueryResponse(
        answer=result.get("answer", ""),
        confidence=_confidence_from_result(result),
        route=result.get("source_type", "unknown"),
        sources=_map_sources(result.get("sources", [])),
        latency_ms=latency_ms,
        trace_id=result.get("trace_id"),
        cached=bool(result.get("_from_cache", False)),
        request_id=request_id,
    )


@router.post("/query/stream", dependencies=[Depends(verify_api_key)])
async def query_stream(req: QueryRequest):
    q: queue.Queue = queue.Queue()
    start = time.time()

    def progress_cb(source_name: str, agent_result: dict):
        q.put({
            "step": source_name,
            "status": "complete",
            "data": {
                "success": agent_result.get("success", False),
                "source": source_name,
            },
            "elapsed_ms": round((time.time() - start) * 1000, 1),
        })

    def run_query():
        try:
            result = get_fusion_agent().query(req.question, progress_cb=progress_cb)
            q.put({
                "step": "answer",
                "status": "done",
                "data": {
                    "answer": result.get("answer", ""),
                    "confidence": _confidence_from_result(result),
                    "route": result.get("source_type", "unknown"),
                    "cached": bool(result.get("_from_cache", False)),
                    "trace_id": result.get("trace_id"),
                    "done": True,
                },
                "elapsed_ms": round((time.time() - start) * 1000, 1),
            })
        except Exception as e:
            q.put({
                "step": "error",
                "status": "error",
                "data": {"error": str(e)},
                "elapsed_ms": round((time.time() - start) * 1000, 1),
            })
        finally:
            q.put(None)  # sentinel

    async def event_generator():
        yield f"data: {json.dumps({'step': 'received', 'status': 'ok', 'data': {'question': req.question}, 'elapsed_ms': 0})}\n\n"

        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, run_query)

        yield f"data: {json.dumps({'step': 'processing', 'status': 'running', 'data': {}, 'elapsed_ms': round((time.time() - start) * 1000, 1)})}\n\n"

        while True:
            try:
                event = await loop.run_in_executor(None, lambda: q.get(timeout=0.1))
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("step") in ("answer", "error"):
                    break
            except queue.Empty:
                continue

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
