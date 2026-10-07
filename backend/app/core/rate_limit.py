import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, status
from app.config import settings

# In-memory rate limiting store: key -> (timestamp, count)
_rate_limit_store: Dict[str, Tuple[float, int]] = {}


def check_rate_limit(request: Request, max_requests: int = 60, window_seconds: int = 60) -> None:
    """
    Simple sliding-window rate limit checker per client IP.
    Can be backed by Redis in distributed production deployments.
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{request.url.path}"
    now = time.time()

    if key in _rate_limit_store:
        window_start, count = _rate_limit_store[key]
        if now - window_start < window_seconds:
            if count >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later.",
                )
            _rate_limit_store[key] = (window_start, count + 1)
        else:
            _rate_limit_store[key] = (now, 1)
    else:
        _rate_limit_store[key] = (now, 1)


def reset_rate_limit_store() -> None:
    _rate_limit_store.clear()
