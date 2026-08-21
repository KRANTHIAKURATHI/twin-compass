"""Shared pytest fixtures: an isolated SQLite file per test (tables created
directly via Base.metadata, no Alembic needed for tests) plus a TestClient
with `get_db` overridden to use it."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.seed import seed


@pytest.fixture()
def db_session():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSessionLocal()
    try:
        seed(session)
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(path)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    # Plain instantiation (no `with`) skips the app's lifespan, so tests never
    # run Alembic/seed/model-training against the real dev database — the
    # isolated `db_session` above is the only database touched.
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def auth_headers(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def register_user(client: TestClient, email: str, password: str, role: str, name: str = "Test User") -> dict:
    """Creates a user with the given role.

    Public self-registration only ever yields a `patient`, so a privileged role
    is created through the admin-only `POST /admin/users` route (authenticating
    as the seeded admin) rather than by asking `/auth/register` for it.
    """
    body = {"email": email, "password": password, "name": name, "role": role}
    if role == "patient":
        resp = client.post("/auth/register", json=body)
    else:
        from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
        admin = auth_headers(client, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)
        resp = client.post("/admin/users", json=body, headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]
