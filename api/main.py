import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.routes import health, agents, query
from agents._singleton import get_fusion_agent

START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("NexusIQ API: pre-warming agents...")
    get_fusion_agent()
    print("NexusIQ API: ready. Docs at /docs")
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="NexusIQ AI API",
    description="Multi-agent business intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(query.router, prefix="/api/v1", tags=["query"])


@app.get("/")
def root():
    return {
        "name": "NexusIQ AI API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "uptime_seconds": round(time.time() - START_TIME, 1),
    }
