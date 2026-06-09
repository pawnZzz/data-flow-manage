import pytest


def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _setup_caller(seed, p, owner, actor, role):
    if role != "owner":
        seed.member(p, actor, role)
        return actor
    return owner


# (角色, 建 schema POST, 建节点 POST, 删 schema DELETE) 期望状态码
# schema/node 写需 editor+；删 schema 需 admin+
MATRIX = [
    ("owner", 201, 201, 204),
    ("admin", 201, 201, 204),
    ("editor", 201, 201, 403),
    ("viewer", 403, 403, 403),
]


@pytest.mark.parametrize("role,schema_code,node_code,del_code", MATRIX, ids=[r[0] for r in MATRIX])
def test_graph_write_endpoints_by_role(client, seed, role, schema_code, node_code, del_code):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)

    # 建 schema（type_key 唯一，用角色名区分避免容器内冲突；图数据每测试已清空）
    tk = f"t_{role}"
    r = client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": tk, "display_name": "T", "fields": []},
                    headers=_auth(seed, caller))
    assert r.status_code == schema_code

    # 建节点（需 schema 先存在；用 owner 确保 schema 在，再用 caller 建节点）
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "shared", "display_name": "S", "fields": []},
                headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": f"n_{role}", "type": "shared"},
                    headers=_auth(seed, caller))
    assert r.status_code == node_code

    # 删 schema（删 shared；owner 先确保存在）
    r = client.delete(f"/api/v1/projects/{p.id}/schemas/shared", headers=_auth(seed, caller))
    # 若该角色建了节点（editor+），shared 可能被占用；为隔离删除权限，删一个空 type
    if del_code == 204:
        # 建一个无节点的空 type 再删，验证删除权限
        client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": "empty", "display_name": "E", "fields": []},
                    headers=_auth(seed, owner))
        r2 = client.delete(f"/api/v1/projects/{p.id}/schemas/empty", headers=_auth(seed, caller))
        assert r2.status_code == 204
    else:
        assert r.status_code == del_code


@pytest.mark.parametrize("role", [r[0] for r in MATRIX])
def test_graph_read_allows_all_members(client, seed, role):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)
    assert client.get(f"/api/v1/projects/{p.id}/schemas", headers=_auth(seed, caller)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, caller)).status_code == 200


# 边写需 editor+，图读 viewer+
EDGE_MATRIX = [
    ("owner", 201, 200),
    ("admin", 201, 200),
    ("editor", 201, 200),
    ("viewer", 403, 200),
]


@pytest.mark.parametrize("role,write_code,read_code", EDGE_MATRIX, ids=[r[0] for r in EDGE_MATRIX])
def test_edge_endpoints_by_role(client, seed, role, write_code, read_code):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)

    # owner 准备 schema + 两节点
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    a = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    b = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "b", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]

    # 写边
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b}, headers=_auth(seed, caller))
    assert r.status_code == write_code

    # 读边列表
    r = client.get(f"/api/v1/projects/{p.id}/edges", headers=_auth(seed, caller))
    assert r.status_code == read_code


@pytest.mark.parametrize("role", [r[0] for r in EDGE_MATRIX])
def test_graph_query_reads_allow_all_members(client, seed, role):
    owner = seed.user("owner_u")
    actor = seed.user("actor_u")
    p = seed.project(owner)
    caller = _setup_caller(seed, p, owner, actor, role)
    # 图查询读端点对全员 200
    assert client.get(f"/api/v1/projects/{p.id}/graph", headers=_auth(seed, caller)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/cycles", headers=_auth(seed, caller)).status_code == 200
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "impact"}, headers=_auth(seed, caller))
    assert r.status_code == 200
