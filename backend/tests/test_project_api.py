def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_create_project_makes_owner(client, seed):
    alice = seed.user("alice")
    r = client.post("/api/v1/projects", json={"name": "数仓"}, headers=_auth(seed, alice))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "数仓"
    assert body["my_role"] == "owner"
    assert body["status"] == "active"


def test_list_only_my_projects(client, seed):
    alice = seed.user("alice")
    bob = seed.user("bob")
    seed.project(alice, name="a-proj")
    seed.project(bob, name="b-proj")
    r = client.get("/api/v1/projects", headers=_auth(seed, alice))
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert names == {"a-proj"}


def test_list_excludes_archived(client, seed):
    alice = seed.user("alice")
    p = seed.project(alice, name="archived", status="archived")
    r = client.get("/api/v1/projects", headers=_auth(seed, alice))
    assert all(item["id"] != p.id for item in r.json())
    r2 = client.get("/api/v1/projects?include_archived=true", headers=_auth(seed, alice))
    assert any(item["id"] == p.id for item in r2.json())


def test_update_project_requires_admin(client, seed):
    alice = seed.user("alice")
    viewer = seed.user("viewer")
    p = seed.project(alice)
    seed.member(p, viewer, "viewer")
    r = client.patch(
        f"/api/v1/projects/{p.id}", json={"name": "new"}, headers=_auth(seed, viewer)
    )
    assert r.status_code == 403


def test_archive_owner_only(client, seed):
    alice = seed.user("alice")
    admin = seed.user("admin")
    p = seed.project(alice)
    seed.member(p, admin, "admin")
    r = client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, admin))
    assert r.status_code == 403
    r2 = client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, alice))
    assert r2.status_code == 204


def test_non_member_403(client, seed):
    alice = seed.user("alice")
    stranger = seed.user("stranger")
    p = seed.project(alice)
    r = client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, stranger))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PERMISSION_DENIED"


def test_get_missing_project_404(client, seed):
    alice = seed.user("alice")
    r = client.get("/api/v1/projects/999999", headers=_auth(seed, alice))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
