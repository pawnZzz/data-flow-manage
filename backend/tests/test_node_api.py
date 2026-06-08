def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _mk_schema(client, seed, p, owner, fields=None):
    client.post(
        f"/api/v1/projects/{p.id}/schemas",
        json={"type_key": "data_task", "display_name": "DT", "fields": fields or []},
        headers=_auth(seed, owner),
    )


def test_create_node_ok(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner,
               [{"name": "engine", "label": "引擎", "type": "enum",
                 "options": ["spark"], "required": True}])
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "ods", "type": "data_task", "ext_props": {"engine": "spark"}},
                    headers=_auth(seed, owner))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "ods"
    assert body["ext_props"]["engine"] == "spark"
    assert body["parent_id"] is None
    assert body["children_count"] == 0


def test_create_node_without_schema_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "x", "type": "unknown_type"},
                    headers=_auth(seed, owner))
    assert r.status_code == 422


def test_create_node_bad_ext_props_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner,
               [{"name": "engine", "label": "引擎", "type": "enum",
                 "options": ["spark"], "required": True}])
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "x", "type": "data_task", "ext_props": {"engine": "flink"}},
                    headers=_auth(seed, owner))
    assert r.status_code == 422


def test_node_name_conflict_409(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    body = {"name": "dup", "type": "data_task"}
    client.post(f"/api/v1/projects/{p.id}/nodes", json=body, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/nodes", json=body, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_get_and_update_node(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    nid = client.post(f"/api/v1/projects/{p.id}/nodes",
                      json={"name": "n", "type": "data_task"},
                      headers=_auth(seed, owner)).json()["id"]
    r = client.patch(f"/api/v1/projects/{p.id}/nodes/{nid}",
                     json={"description": "d", "priority": "P1"},
                     headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["description"] == "d"
    assert r.json()["priority"] == "P1"


def test_list_nodes_filter_by_type_and_name(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    for nm in ["alpha", "beta"]:
        client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": nm, "type": "data_task"}, headers=_auth(seed, owner))
    r = client.get(f"/api/v1/projects/{p.id}/nodes?name=alph", headers=_auth(seed, owner))
    assert {n["name"] for n in r.json()} == {"alpha"}
    r2 = client.get(f"/api/v1/projects/{p.id}/nodes?type=data_task", headers=_auth(seed, owner))
    assert {n["name"] for n in r2.json()} == {"alpha", "beta"}


def test_delete_node(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    _mk_schema(client, seed, p, owner)
    nid = client.post(f"/api/v1/projects/{p.id}/nodes",
                      json={"name": "n", "type": "data_task"},
                      headers=_auth(seed, owner)).json()["id"]
    r = client.delete(f"/api/v1/projects/{p.id}/nodes/{nid}", headers=_auth(seed, owner))
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/projects/{p.id}/nodes/{nid}", headers=_auth(seed, owner))
    assert r2.status_code == 404


def test_node_write_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer")
    _mk_schema(client, seed, p, owner)
    r = client.post(f"/api/v1/projects/{p.id}/nodes",
                    json={"name": "n", "type": "data_task"}, headers=_auth(seed, viewer))
    assert r.status_code == 403
