def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_preview_marks_existing(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "table", "display_name": "table", "fields": []},
                headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes",
                json={"name": "src.a", "type": "table"}, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                    json={"sql": "INSERT INTO dw.t SELECT * FROM src.a"},
                    headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    by = {t["name"]: t for t in body["tables"]}
    assert by["src.a"]["exists"] is True and by["src.a"]["node_id"]
    assert by["dw.t"]["exists"] is False
    assert {"source": "dw.t", "target": "src.a", "edge_type": "data_flow"} in body["dependencies"]


def test_preview_does_not_write(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                json={"sql": "INSERT INTO dw.t SELECT * FROM src.a"},
                headers=_auth(seed, owner))
    r = client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, owner))
    assert r.json() == []


def test_preview_syntax_error_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                    json={"sql": "INSERT INTO"}, headers=_auth(seed, owner))
    assert r.status_code == 422
    assert r.json()["error"]["details"].get("code") == "SQL_PARSE_ERROR"


def test_commit_creates_all(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                    json={"tables": [{"name": "dw.t"}, {"name": "src.a"}],
                          "dependencies": [{"source": "dw.t", "target": "src.a"}]},
                    headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json() == {"created_nodes": 2, "reused_nodes": 0,
                        "created_edges": 1, "skipped_edges": 0}
    names = {n["name"] for n in client.get(f"/api/v1/projects/{p.id}/nodes",
                                           headers=_auth(seed, owner)).json()}
    assert {"dw.t", "src.a"} <= names
    edges = client.get(f"/api/v1/projects/{p.id}/edges", headers=_auth(seed, owner)).json()
    assert len(edges) == 1


def test_commit_reuses_and_skips(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    body = {"tables": [{"name": "dw.t"}, {"name": "src.a"}],
            "dependencies": [{"source": "dw.t", "target": "src.a"}]}
    client.post(f"/api/v1/projects/{p.id}/sql-import/commit", json=body, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit", json=body, headers=_auth(seed, owner))
    assert r.json() == {"created_nodes": 0, "reused_nodes": 2,
                        "created_edges": 0, "skipped_edges": 1}


def test_commit_skips_unresolved_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                    json={"tables": [{"name": "only"}],
                          "dependencies": [{"source": "only", "target": "ghost"}]},
                    headers=_auth(seed, owner))
    assert r.json()["created_nodes"] == 1
    assert r.json()["skipped_edges"] == 1


def test_commit_skips_self_loop_edge(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    # 用户编辑后的 body 可能含自引用依赖（source==target）→ edge_service 报 SELF_LOOP → 跳过
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                    json={"tables": [{"name": "t"}],
                          "dependencies": [{"source": "t", "target": "t"}]},
                    headers=_auth(seed, owner))
    assert r.json()["created_nodes"] == 1
    assert r.json()["created_edges"] == 0
    assert r.json()["skipped_edges"] == 1


def test_sql_import_requires_editor(client, seed):
    owner = seed.user("owner"); viewer = seed.user("viewer")
    p = seed.project(owner); seed.member(p, viewer, "viewer")
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/preview",
                    json={"sql": "SELECT 1"}, headers=_auth(seed, viewer))
    assert r.status_code == 403
    r2 = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                     json={"tables": [], "dependencies": []}, headers=_auth(seed, viewer))
    assert r2.status_code == 403
