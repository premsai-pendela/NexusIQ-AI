import os
from fastapi import Request, HTTPException
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(request: Request):
    keys_env = os.getenv("NEXUSIQ_API_KEYS", "")
    if not keys_env:
        return  # dev mode — no auth
    valid_keys = {k.strip() for k in keys_env.split(",") if k.strip()}
    key = request.headers.get("X-API-Key")
    if not key or key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
