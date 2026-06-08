import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from typing_extensions import Annotated

from app.db.mysql import get_session
from app.deps import ProjectContext, require_role
from app.exceptions import register_exception_handlers
from app.models import MemberRole


@pytest.fixture
def role_app(mysql_engine):
    from sqlalchemy.orm import sessionmaker

    TestingSession = sessionmaker(bind=mysql_engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/p/{pid}/admin")
    def _admin(ctx: Annotated[ProjectContext, Depends(require_role(MemberRole.admin))]):
        return {"role": ctx.membership.role.value}

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_admin_allows_owner(role_app, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = role_app.get(f"/p/{p.id}/admin", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["role"] == "owner"


def test_admin_rejects_viewer(role_app, seed):
    owner = seed.user("owner")
    viewer = seed.user("viewer")
    p = seed.project(owner)
    seed.member(p, viewer, "viewer")
    r = role_app.get(f"/p/{p.id}/admin", headers=_auth(seed, viewer))
    assert r.status_code == 403


def test_rejects_non_member(role_app, seed):
    owner = seed.user("owner")
    stranger = seed.user("stranger")
    p = seed.project(owner)
    r = role_app.get(f"/p/{p.id}/admin", headers=_auth(seed, stranger))
    assert r.status_code == 403


def test_404_when_project_missing(role_app, seed):
    owner = seed.user("owner")
    r = role_app.get("/p/999999/admin", headers=_auth(seed, owner))
    assert r.status_code == 404
