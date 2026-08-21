class NotFoundError(Exception):
    """Raised by services when a requested aggregate doesn't exist (or is
    soft-deleted). Translated to a 404 by the handler registered in main.py,
    so routers never need their own try/except for this case."""


class ForbiddenError(Exception):
    """Raised by services when an authenticated user is not permitted to
    access/mutate a specific resource (e.g. a `patient`-role user reading
    another patient's record). Translated to a 403 by the handler registered
    in main.py."""


class ValidationError(Exception):
    """Raised by services when a request is well-formed but semantically
    invalid (e.g. a required identifier is missing). Translated to a 400 by the
    handler registered in main.py — distinct from FastAPI's own 422, which
    covers schema-level violations."""
