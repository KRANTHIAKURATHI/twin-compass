"""An unhandled server-side error must return a generic 500 body.

Driver messages, SQL fragments and stack traces are diagnostic detail for the
server log, not for the client — leaking them tells an attacker the schema.
"""

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.main import app

_SECRET_DETAIL = 'relation "patients" does not exist at character 42'


def _client_without_reraise(db_session):
    """A TestClient that lets the app's own handler produce the 500 response.

    The default TestClient re-raises server exceptions instead of returning
    them, which would bypass the very handler under test.
    """
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


def test_unhandled_error_returns_generic_500(db_session):
    """Uses a throwaway route rather than monkeypatching a handler, because
    FastAPI captures the endpoint function at registration time."""
    path = "/__test_boom__"

    @app.get(path)
    def _boom():
        raise OperationalError(f"SELECT * FROM patients -- {_SECRET_DETAIL}", {}, Exception(_SECRET_DETAIL))

    gen = _client_without_reraise(db_session)
    client = next(gen)
    try:
        resp = client.get(path)
    finally:
        next(gen, None)
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != path]

    assert resp.status_code == 500
    body = resp.text
    assert resp.json() == {"detail": "An unexpected internal error occurred."}
    for leak in ("patients", "SELECT", "Traceback", "OperationalError", "sqlalchemy"):
        assert leak not in body


def test_known_domain_errors_are_not_swallowed_by_the_catch_all(client):
    """The catch-all must not shadow the specific 401/403/404 handlers."""
    assert client.get("/patients").status_code == 401

    from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
    from tests.conftest import auth_headers

    headers = auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)
    assert client.get("/patients/does-not-exist", headers=headers).status_code in (200, 404)

    client.post("/auth/register", json={"name": "Scoped", "email": "scoped-err@example.com",
                                        "password": "Secret123!", "role": "patient"})
    pat = auth_headers(client, "scoped-err@example.com", "Secret123!")
    assert client.get("/admin/users", headers=pat).status_code == 403


def test_validation_error_still_returns_422(client):
    from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
    from tests.conftest import auth_headers

    headers = auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)
    resp = client.post("/patients", json={"age": "not-a-number"}, headers=headers)
    assert resp.status_code == 422
