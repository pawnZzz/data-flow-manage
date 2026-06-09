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


def test_create_and_get_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b, "edge_type": "trigger"},
                    headers=_auth(seed, owner))
    assert r.status_code == 201
    body = r.json()
    assert body["warnings"]["creates_cycle"] is False
    eid = body["edge"]["id"]
    assert body["edge"]["source_id"] == a and body["edge"]["target_id"] == b
    r2 = client.get(f"/api/v1/projects/{p.id}/edges/{eid}", headers=_auth(seed, owner))
    assert r2.status_code == 200
    assert r2.json()["edge_type"] == "trigger"


def test_create_edge_missing_endpoint_404(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": "nope"}, headers=_auth(seed, owner))
    assert r.status_code == 404


def test_duplicate_edge_409(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    body = {"source_id": a, "target_id": b}
    client.post(f"/api/v1/projects/{p.id}/edges", json=body, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/edges", json=body, headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "EDGE_EXISTS"


def test_self_loop_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": a}, headers=_auth(seed, owner))
    assert r.status_code == 422
    assert r.json()["error"]["details"].get("code") == "SELF_LOOP"


def test_list_edges_filter(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    c = _mk_node(client, seed, p, owner, "c")
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": a, "target_id": b, "edge_type": "trigger"},
                headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": a, "target_id": c, "edge_type": "data_flow"},
                headers=_auth(seed, owner))
    r = client.get(f"/api/v1/projects/{p.id}/edges?source_id={a}", headers=_auth(seed, owner))
    assert len(r.json()) == 2
    r2 = client.get(f"/api/v1/projects/{p.id}/edges?edge_type=trigger", headers=_auth(seed, owner))
    assert {e["target_id"] for e in r2.json()} == {b}


def test_update_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    eid = client.post(f"/api/v1/projects/{p.id}/edges",
                      json={"source_id": a, "target_id": b},
                      headers=_auth(seed, owner)).json()["edge"]["id"]
    r = client.patch(f"/api/v1/projects/{p.id}/edges/{eid}",
                     json={"strength": "weak", "description": "soft"},
                     headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["strength"] == "weak"
    assert r.json()["description"] == "soft"


def test_delete_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    eid = client.post(f"/api/v1/projects/{p.id}/edges",
                      json={"source_id": a, "target_id": b},
                      headers=_auth(seed, owner)).json()["edge"]["id"]
    r = client.delete(f"/api/v1/projects/{p.id}/edges/{eid}", headers=_auth(seed, owner))
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/projects/{p.id}/edges/{eid}", headers=_auth(seed, owner))
    assert r2.status_code == 404


def test_edge_write_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer"); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b}, headers=_auth(seed, viewer))
    assert r.status_code == 403


def test_create_edge_cycle_warning(client, seed):
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a"); b = _mk_node(client, seed, p, owner, "b")
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": a, "target_id": b}, headers=_auth(seed, owner))
    # b -> a 制造环：新建这条边时应预警 creates_cycle
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": b, "target_id": a}, headers=_auth(seed, owner))
    assert r.status_code == 201
    assert r.json()["warnings"]["creates_cycle"] is True
