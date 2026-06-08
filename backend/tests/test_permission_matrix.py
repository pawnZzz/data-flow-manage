import pytest


def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


# (角色, 改项目 PATCH, 管成员 POST, 删项目 DELETE) 期望状态码
# 改项目/管成员需 admin+；删项目需 owner
MATRIX = [
    ("owner", 200, 201, 204),
    ("admin", 200, 201, 403),
    ("editor", 403, 403, 403),
    ("viewer", 403, 403, 403),
]


@pytest.mark.parametrize("role,patch_code,member_code,delete_code", MATRIX)
def test_write_endpoints_by_role(client, seed, role, patch_code, member_code, delete_code):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    seed.user("newbie")
    p = seed.project(owner)
    if role != "owner":
        seed.member(p, actor, role)
        caller = actor
    else:
        caller = owner

    # 改项目
    r = client.patch(
        f"/api/v1/projects/{p.id}", json={"name": "x"}, headers=_auth(seed, caller)
    )
    assert r.status_code == patch_code

    # 管成员（添加 newbie）
    r = client.post(
        f"/api/v1/projects/{p.id}/members",
        json={"username": "newbie", "role": "viewer"},
        headers=_auth(seed, caller),
    )
    assert r.status_code == member_code

    # 删项目
    r = client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, caller))
    assert r.status_code == delete_code


@pytest.mark.parametrize("role", ["owner", "admin", "editor", "viewer"])
def test_read_endpoints_allow_all_members(client, seed, role):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    if role != "owner":
        seed.member(p, actor, role)
        caller = actor
    else:
        caller = owner
    r = client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, caller))
    assert r.status_code == 200
    r = client.get(f"/api/v1/projects/{p.id}/members", headers=_auth(seed, caller))
    assert r.status_code == 200
