"""
Domain exception hierarchy.

Mirrors the error-category table in the FastAPI Backend Architecture
Blueprint Section 16. Every exception here is mapped to the standard error
envelope (`{"error": {"code", "message", "field", "request_id"}}`, System
Architecture Blueprint Section 12.1) by the global handler registered in
`app/middleware/exception_handler.py`. Route handlers and services raise
these directly rather than returning HTTPException with ad hoc bodies, so
the response shape is guaranteed consistent no matter which layer raises.
"""
from __future__ import annotations


class AppError(Exception):
    """Base for all domain exceptions. `status_code` and `code` drive the HTTP mapping."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    """Invalid credentials, missing/expired/invalid token."""

    status_code = 401
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    """Authenticated, but not permitted to perform this action."""

    status_code = 403
    code = "AUTHORIZATION_ERROR"


class ConflictError(AppError):
    """E.g. registering an email that already has an account."""

    status_code = 409
    code = "CONFLICT"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class UpstreamServiceError(AppError):
    """Supabase Auth (or any external dependency) failed or timed out."""

    status_code = 502
    code = "UPSTREAM_SERVICE_ERROR"


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
