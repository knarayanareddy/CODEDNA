"""Middleware for CodeDNA daemon."""
import logging
import time
from collections import defaultdict
from threading import Lock
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Endpoints exempt from X-CodeDNA-Client header validation
EXEMPT_ENDPOINTS = {
    "/health",
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Known valid client identifiers
VALID_CLIENT_IDS = {
    "cli",
    "vscode-extension",
    "dashboard",
    "pre-commit-hook",
    "api-test",
    "testclient",
}


class ClientValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates X-CodeDNA-Client header per design spec §8.1 and §9.3.
    
    Prevents CSRF attacks by ensuring requests include a recognized client identifier.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Exempt health check and documentation endpoints
        if request.url.path in EXEMPT_ENDPOINTS:
            return await call_next(request)
        
        # Check for X-CodeDNA-Client header
        client_id = request.headers.get("X-CodeDNA-Client")
        
        if not client_id:
            logger.warning(f"Request missing X-CodeDNA-Client header: {request.url.path}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "MISSING_CLIENT_HEADER",
                        "message": "X-CodeDNA-Client header is required for all API requests"
                    }
                }
            )
        
        # Normalize client ID (lowercase, strip whitespace)
        normalized_id = client_id.lower().strip()
        
        # For now, log unknown clients but allow them (permissive mode)
        # In stricter deployments, reject unknown clients
        if normalized_id not in VALID_CLIENT_IDS:
            logger.debug(f"Unknown X-CodeDNA-Client: {client_id}")
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware per design spec §9.3.
    
    Limits requests to prevent abuse:
    - 100 requests/minute per client
    - 1000 requests/minute per IP (for local protection)
    """
    
    def __init__(self, app, requests_per_minute: int = 100, ip_requests_per_minute: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.ip_requests_per_minute = ip_requests_per_minute
        self._client_requests: dict = defaultdict(list)  # client_id -> list of timestamps
        self._ip_requests: dict = defaultdict(list)  # ip -> list of timestamps
        self._lock = Lock()
    
    def _clean_old_requests(self, timestamps: list, window_seconds: int = 60) -> list:
        """Remove timestamps outside the rate limit window."""
        now = time.time()
        cutoff = now - window_seconds
        return [ts for ts in timestamps if ts > cutoff]
    
    def _is_rate_limited(self, identifier: str, timestamps: list, limit: int) -> bool:
        """Check if an identifier has exceeded the rate limit."""
        now = time.time()
        window_start = now - 60
        
        # Count requests in the last minute
        recent_requests = [ts for ts in timestamps if ts > window_start]
        
        if len(recent_requests) >= limit:
            return True
        
        # Add current request timestamp
        timestamps.append(now)
        return False
    
    async def dispatch(self, request: Request, call_next):
        # Exempt health and documentation endpoints
        if request.url.path in EXEMPT_ENDPOINTS:
            return await call_next(request)
        
        client_id = request.headers.get("X-CodeDNA-Client", "unknown").lower()
        client_ip = request.client.host if request.client else "unknown"
        
        with self._lock:
            # Check client-based rate limit
            client_ts = self._client_requests[client_id]
            client_ts[:] = self._clean_old_requests(client_ts)
            
            if self._is_rate_limited(client_id, client_ts, self.requests_per_minute):
                logger.warning(f"Rate limit exceeded for client: {client_id}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute."
                        },
                        "retry_after": 60
                    },
                    headers={"Retry-After": "60"}
                )
            
            # Check IP-based rate limit
            ip_ts = self._ip_requests[client_ip]
            ip_ts[:] = self._clean_old_requests(ip_ts)
            
            if self._is_rate_limited(client_ip, ip_ts, self.ip_requests_per_minute):
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit exceeded. Maximum {self.ip_requests_per_minute} requests per minute per IP."
                        },
                        "retry_after": 60
                    },
                    headers={"Retry-After": "60"}
                )
        
        return await call_next(request)


class LocalhostOnlyMiddleware(BaseHTTPMiddleware):
    """
    Middleware that rejects requests from non-loopback addresses in production.
    Allows test clients and health check endpoints.
    """
    
    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client else None
        
        # Allow test client (used by FastAPI TestClient)
        if client_host and client_host in ("testclient", "127.0.0.1", "::1", "localhost"):
            return await call_next(request)
        
        # Allow health and root endpoints without local check
        if request.url.path in EXEMPT_ENDPOINTS:
            return await call_next(request)
        
        # Check if it's loopback
        if client_host and self._is_loopback(client_host):
            return await call_next(request)
        
        # Reject non-loopback
        logger.warning(f"Non-localhost request rejected from {client_host}")
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "NON_LOCALHOST_REJECTED",
                    "message": "Requests from non-loopback addresses are not permitted"
                }
            }
        )
    
    def _is_loopback(self, host: str) -> bool:
        return host and (host.startswith("127.") or host == "::1" or host == "localhost")
