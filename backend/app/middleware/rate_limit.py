"""Rate limiting middleware for FastAPI — simple in-memory sliding window."""

import time
from collections import defaultdict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


class RateLimiter:
    """Per-IP rate limiter using an in-memory sliding window."""
    
    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
    
    async def __call__(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Prune old entries
        self._requests[ip] = [t for t in self._requests[ip] if now - t < self.window_seconds]
        
        if len(self._requests[ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": self.window_seconds}
            )
        
        self._requests[ip].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_requests - len(self._requests[ip])))
        return response


rate_limiter = RateLimiter(max_requests=120, window_seconds=60)
