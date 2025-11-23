"""Custom middleware for tracking metrics and other cross-cutting concerns."""

import time
from typing import Callable

import sentry_sdk
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import (
    bind_context,
    clear_context,
)
from app.core.metrics import (
    db_connections,
    http_request_duration_seconds,
    http_requests_total,
)
from app.utils.jwk_auth import verify_jwt


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking HTTP request metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track metrics for each request.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response: The response from the application
        """
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(method=request.method, endpoint=request.url.path, status=status_code).inc()

            http_request_duration_seconds.labels(method=request.method, endpoint=request.url.path).observe(duration)

        return response


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Middleware for adding user_id and conversation_id to logging context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Extract user_id from JWK token and add to logging context.

        Also sets Sentry user context for better error tracking.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response: The response from the application
        """
        try:
            # Clear any existing context from previous requests
            clear_context()

            # Extract token from Authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

                try:
                    # Verify JWK token and extract user_id from "sub" claim
                    payload = verify_jwt(token)
                    user_id = payload.get("sub")

                    if user_id:
                        # Bind user_id to logging context
                        bind_context(user_id=user_id)

                        # Set Sentry user context
                        sentry_sdk.set_user(
                            {
                                "id": user_id,
                                "email": payload.get("email"),
                            }
                        )

                except Exception:
                    # Token is invalid, but don't fail the request - let the auth dependency handle it
                    pass

            # Process the request
            response = await call_next(request)

            return response

        finally:
            # Always clear context after request is complete to avoid leaking to other requests
            clear_context()
