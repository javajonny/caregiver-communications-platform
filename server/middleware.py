"""
Request Context Middleware

Extracts client IP and User-Agent from incoming requests
and stores them in request.state for use by audit logging.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts request context (IP, User-Agent) and stores it
    in request.state for downstream use by audit logging.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Extract client IP (handles proxies via X-Forwarded-For if needed)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take first IP if multiple (original client)
            request.state.client_ip = forwarded_for.split(",")[0].strip()
        else:
            request.state.client_ip = request.client.host if request.client else None
        
        # Extract User-Agent
        request.state.user_agent = request.headers.get("user-agent")
        
        return await call_next(request)
