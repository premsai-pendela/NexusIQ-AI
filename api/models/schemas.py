from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Any
from datetime import datetime


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    source: Literal["auto", "sql", "rag", "web", "all"] = "auto"
    session_id: Optional[str] = None


class SourceCitation(BaseModel):
    type: str  # "sql", "rag", "web"
    content: str
    filename: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    confidence: str  # HIGH / MEDIUM / LOW / UNKNOWN
    route: str
    sources: List[SourceCitation]
    latency_ms: float
    trace_id: Optional[str] = None
    cached: bool = False
    request_id: str


class StreamEvent(BaseModel):
    step: str
    status: str
    data: dict = {}
    elapsed_ms: float


class HealthResponse(BaseModel):
    status: str  # "healthy" / "degraded"
    agents: dict
    production_features: dict = {}
    chroma_chunks: int
    cache_entries: int
    uptime_seconds: float
    timestamp: str


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str
