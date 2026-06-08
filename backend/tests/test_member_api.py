def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_add_member_by_username(client, seed):
    owner = seed.user("owner")
    seed.user("bob")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "bob", "role": "editor"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 201
    assert r.json()["username"] == "bob"
    assert r.json()["role"] == "editor"


def test_add_member_by_email(client, seed):
    owner = seed.user("owner")
    seed.user("bob", email="bob@corp.com")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"email": "bob@corp.com", "role": "viewer"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 201
    assert r.json()["user_id"] is not None
    assert r.json()["username"] == "bob"
    assert r.json()["role"] == "viewer"


def test_add_member_unknown_404(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "ghost", "role": "viewer"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 404


def test_add_member_duplicate_409(client, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "bob", "role": "editor"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 409


def test_change_role(client, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    r = client.patch(
        f"/api/v1/projects/{p.id}/members/{bob.id}",
        json={"role": "editor"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 200
    assert r.json()["role"] == "editor"


def test_cannot_demote_last_owner(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.patch(
        f"/api/v1/projects/{p.id}/members/{owner.id}",
        json={"role": "admin"},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 409


def test_admin_cannot_promote_to_owner(client, seed):
    owner = seed.user("owner")
    admin = seed.user("admin")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, admin, "admin")
    seed.member(p, bob, "editor")
    r = client.patch(
        f"/api/v1/projects/{p.id}/members/{bob.id}",
        json={"role": "owner"},
        headers=_auth(seed, admin),
    )
    assert r.status_code == 403


def test_cannot_remove_owner(client, seed):
    owner = seed.user("owner")
    admin = seed.user("admin")
    p = seed.project(owner)
    seed.member(p, admin, "admin")
    r = client.delete(
        f"/api/v1/projects/{p.id}/members/{owner.id}",
        headers=_auth(seed, admin),
    )
    assert r.status_code == 403


def test_remove_member_ok(client, seed):
    owner = seed.user("owner")
    bob = seed.user("bob")
    p = seed.project(owner)
    seed.member(p, bob, "viewer")
    r = client.delete(
        f"/api/v1/projects/{p.id}/members/{bob.id}",
        headers=_auth(seed, owner),
    )
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/projects/{p.id}/members", headers=_auth(seed, owner))
    assert all(m["user_id"] != bob.id for m in r2.json())
