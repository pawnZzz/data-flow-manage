import pytest
from sqlalchemy.orm import sessionmaker

from app.models import Project, ProjectMember, User


@pytest.fixture(autouse=True)
def _clear_users(mysql_engine):
    Session = sessionmaker(bind=mysql_engine)
    s = Session()
    s.query(ProjectMember).delete()
    s.query(Project).delete()
    s.query(User).delete()
    s.commit()
    s.close()


def _register(client, username="alice", email="alice@x.com", password="secret"):
    return client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def _token(client, username="alice", password="secret"):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


def test_register_then_login(client):
    r = _register(client)
    assert r.status_code == 201
    assert r.json()["username"] == "alice"

    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_register_duplicate_returns_409_structured(client):
    _register(client)
    r = _register(client)
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "CONFLICT"
    assert "message" in body["error"]


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_ERROR"


def test_me_with_token(client):
    _register(client)
    token = _token(client)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_login_wrong_password_401(client):
    _register(client)
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "nope"})
    assert r.status_code == 401


def test_update_me(client):
    _register(client)
    token = _token(client)
    r = client.patch(
        "/api/v1/auth/me",
        json={"display_name": "Alice L"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Alice L"


def test_change_password_then_login(client):
    _register(client)
    token = _token(client)
    r = client.post(
        "/api/v1/auth/password",
        json={"old_password": "secret", "new_password": "brandnew"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "brandnew"})
    assert r.status_code == 200


def test_validation_error_uses_envelope(client):
    # username too short triggers 422
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "ab", "email": "a@b.com", "password": "secret"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
