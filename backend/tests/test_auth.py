def test_login_success(client):
    from app.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD

    resp = client.post("/auth/login", json={"email": DEFAULT_ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == DEFAULT_ADMIN_EMAIL
    assert body["accessToken"]


def test_login_wrong_password(client):
    from app.seed import DEFAULT_ADMIN_EMAIL

    resp = client.post("/auth/login", json={"email": DEFAULT_ADMIN_EMAIL, "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401


def test_register_and_login(client):
    resp = client.post("/auth/register", json={
        "email": "doc@example.com", "password": "Password123!", "name": "Dr. Test", "role": "doctor",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "doc@example.com"

    resp = client.post("/auth/login", json={"email": "doc@example.com", "password": "Password123!"})
    assert resp.status_code == 200


def test_register_duplicate_email_rejected(client):
    client.post("/auth/register", json={
        "email": "dup@example.com", "password": "Password123!", "name": "First", "role": "doctor",
    })
    resp = client.post("/auth/register", json={
        "email": "dup@example.com", "password": "Password123!", "name": "Second", "role": "doctor",
    })
    assert resp.status_code == 409


def test_me_requires_valid_token(client):
    resp = client.get("/patients")
    assert resp.status_code == 401

    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
