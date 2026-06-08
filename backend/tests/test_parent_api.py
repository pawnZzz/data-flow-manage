def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _mk_schema(client, seed, p, owner):
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))


def _mk_node(client, seed, p, owner, name):
    return client.post(f"/api/v1/projects/{p.id}/nodes",
                       json={"name": name, "type": "t"},
                       headers=_auth(seed, owner)).json()["id"]


def test_set_and_get_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    parent = _mk_node(client, seed, p, owner, "parent")
    r = client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent",
                    json={"parent_id": parent}, headers=_auth(seed, owner))
    assert r.status_code == 204
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] == parent


def test_list_children_and_descendants(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")  # 顶
    b = _mk_node(client, seed, p, owner, "b")  # a 的子
    c = _mk_node(client, seed, p, owner, "c")  # b 的子
    client.post(f"/api/v1/projects/{p.id}/nodes/{b}/parent", json={"parent_id": a}, headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes/{c}/parent", json={"parent_id": b}, headers=_auth(seed, owner))
    children = client.get(f"/api/v1/projects/{p.id}/nodes/{a}/children", headers=_auth(seed, owner)).json()
    assert {n["name"] for n in children} == {"b"}
    desc = client.get(f"/api/v1/projects/{p.id}/nodes/{a}/descendants", headers=_auth(seed, owner)).json()
    assert {n["name"] for n in desc} == {"b", "c"}


def test_parent_cycle_rejected(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    client.post(f"/api/v1/projects/{p.id}/nodes/{b}/parent", json={"parent_id": a}, headers=_auth(seed, owner))
    # 把 a 的父设为 b → 成环
    r = client.post(f"/api/v1/projects/{p.id}/nodes/{a}/parent",
                    json={"parent_id": b}, headers=_auth(seed, owner))
    assert r.status_code == 422
    assert r.json()["error"]["details"].get("code") == "PARENT_CYCLE"


def test_self_parent_rejected(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    r = client.post(f"/api/v1/projects/{p.id}/nodes/{a}/parent",
                    json={"parent_id": a}, headers=_auth(seed, owner))
    assert r.status_code == 422


def test_reparent_single_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    p1 = _mk_node(client, seed, p, owner, "p1")
    p2 = _mk_node(client, seed, p, owner, "p2")
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": p1}, headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": p2}, headers=_auth(seed, owner))
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] == p2  # 单一父亲，换成 p2


def test_clear_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    parent = _mk_node(client, seed, p, owner, "parent")
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": parent}, headers=_auth(seed, owner))
    r = client.delete(f"/api/v1/projects/{p.id}/nodes/{child}/parent", headers=_auth(seed, owner))
    assert r.status_code == 204
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] is None


def test_delete_parent_orphans_child(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    child = _mk_node(client, seed, p, owner, "child")
    parent = _mk_node(client, seed, p, owner, "parent")
    client.post(f"/api/v1/projects/{p.id}/nodes/{child}/parent", json={"parent_id": parent}, headers=_auth(seed, owner))
    client.delete(f"/api/v1/projects/{p.id}/nodes/{parent}", headers=_auth(seed, owner))
    detail = client.get(f"/api/v1/projects/{p.id}/nodes/{child}", headers=_auth(seed, owner)).json()
    assert detail["parent_id"] is None  # 父删除后 child 变顶层，自身仍在
