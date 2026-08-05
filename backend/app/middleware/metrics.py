"""Prometheus metrics middleware for FastAPI."""

import logging
import time
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import track_request, record_error

logger = logging.getLogger(__name__)


async def metrics_middleware(request: Request, call_next) -> Response:
    """Middleware to track HTTP metrics."""
    start_time = time.time()
    
    response = await call_next(request)
    
    response_time = time.time() - start_time
    
    # Track request metrics
    track_request(request, response_time, response.status_code)
    
    # Track errors
    if response.status_code >= 500:
        record_error(error_type=f"http_{response.status_code}")
    
    return response
