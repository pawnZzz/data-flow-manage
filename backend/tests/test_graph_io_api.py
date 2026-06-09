def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _build_graph(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    for nm in ["a", "b", "child"]:
        client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": nm, "type": "t"},
                    headers=_auth(seed, owner))
    ids = {n["name"]: n["id"] for n in
           client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, owner)).json()}
    client.post(f"/api/v1/projects/{p.id}/nodes/{ids['child']}/parent",
                json={"parent_id": ids["a"]}, headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": ids["a"], "target_id": ids["b"]}, headers=_auth(seed, owner))
    return owner, p


def test_export_shape(client, seed):
    owner, p = _build_graph(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert {s["type_key"] for s in body["schemas"]} == {"t"}
    names = [n["name"] for n in body["nodes"]]
    assert names == sorted(names)
    assert all("id" not in n for n in body["nodes"])
    assert all("id" not in s for s in body["schemas"])  # schema UUID/时间戳不泄漏
    child = next(n for n in body["nodes"] if n["name"] == "child")
    assert child["parent"] == "a"
    assert {"source": "a", "target": "b"} == {k: body["edges"][0][k] for k in ("source", "target")}


def test_export_requires_member(client, seed):
    owner = seed.user("owner"); outsider = seed.user("outsider")
    p = seed.project(owner)
    r = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, outsider))
    assert r.status_code == 403


def test_roundtrip_export_import(client, seed):
    owner, p = _build_graph(client, seed)
    exported = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, owner)).json()
    p2 = seed.project(owner, name="proj2")
    r = client.post(f"/api/v1/projects/{p2.id}/import", json=exported, headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert body["created_schemas"] == 1
    assert body["created_nodes"] == 3
    assert body["created_edges"] == 1
    assert body["set_parents"] == 1
    exported2 = client.get(f"/api/v1/projects/{p2.id}/export", headers=_auth(seed, owner)).json()
    assert {n["name"] for n in exported2["nodes"]} == {"a", "b", "child"}
    child2 = next(n for n in exported2["nodes"] if n["name"] == "child")
    assert child2["parent"] == "a"
    assert exported2["edges"][0]["source"] == "a" and exported2["edges"][0]["target"] == "b"


def test_import_merge_idempotent(client, seed):
    owner, p = _build_graph(client, seed)
    exported = client.get(f"/api/v1/projects/{p.id}/export", headers=_auth(seed, owner)).json()
    r = client.post(f"/api/v1/projects/{p.id}/import", json=exported, headers=_auth(seed, owner))
    body = r.json()
    assert body["created_schemas"] == 0 and body["reused_schemas"] == 1
    assert body["created_nodes"] == 0 and body["reused_nodes"] == 3
    assert body["created_edges"] == 0 and body["skipped_edges"] == 1


def test_import_skips_dup_edge_and_missing_parent(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    payload = {
        "schemas": [{"type_key": "t", "display_name": "T", "fields": []}],
        "nodes": [
            {"name": "a", "type": "t", "description": None, "owner": None,
             "department": None, "system": None, "priority": None, "tags": [],
             "ext_props": {}, "is_critical": False, "parent": "ghost"},
            {"name": "b", "type": "t", "description": None, "owner": None,
             "department": None, "system": None, "priority": None, "tags": [],
             "ext_props": {}, "is_critical": False, "parent": None},
        ],
        "edges": [
            {"source": "a", "target": "b", "edge_type": "data_flow", "description": None,
             "is_required": True, "strength": "strong", "ext_props": {}},
            {"source": "a", "target": "b", "edge_type": "data_flow", "description": None,
             "is_required": True, "strength": "strong", "ext_props": {}},
            {"source": "a", "target": "ghost", "edge_type": "data_flow", "description": None,
             "is_required": True, "strength": "strong", "ext_props": {}},
        ],
    }
    r = client.post(f"/api/v1/projects/{p.id}/import", json=payload, headers=_auth(seed, owner))
    body = r.json()
    assert body["created_nodes"] == 2
    assert body["set_parents"] == 0
    assert body["created_edges"] == 1
    assert body["skipped_edges"] == 2


def test_import_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer")
    r = client.post(f"/api/v1/projects/{p.id}/import",
                    json={"schemas": [], "nodes": [], "edges": []}, headers=_auth(seed, viewer))
    assert r.status_code == 403


def test_import_blocked_on_archived(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/import",
                    json={"schemas": [], "nodes": [], "edges": []}, headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ACTIVE"


def test_import_bad_data_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/import",
                    json={"nodes": [{"type": "t"}]}, headers=_auth(seed, owner))
    assert r.status_code == 422
