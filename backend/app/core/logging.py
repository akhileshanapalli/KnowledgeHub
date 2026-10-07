import contextvars
import logging
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to hold request-scoped correlation ID
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")


class StructuredLogRecord(logging.LogRecord):
    def getMessage(self) -> str:
        msg = super().getMessage()
        cid = correlation_id_ctx.get()
        if cid:
            return f"[req_id={cid}] {msg}"
        return msg


def setup_logging(debug: bool = True) -> None:
    logging.setLogRecordFactory(StructuredLogRecord)
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Read or generate Request/Correlation ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = correlation_id_ctx.set(req_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            process_time = (time.perf_counter() - start_time) * 1000
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
            return response
        finally:
            correlation_id_ctx.reset(token)
