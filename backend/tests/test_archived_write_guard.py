def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _archived_project_with_schema(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    a = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    b = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "b", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))  # → archived
    return owner, p, a, b


def test_archived_blocks_node_create(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "c", "type": "t"},
                    headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ACTIVE"


def test_archived_blocks_edge_create(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": a, "target_id": b}, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_schema_create(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": "t2", "display_name": "T2", "fields": []},
                    headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_sql_import(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/sql-import/commit",
                    json={"tables": [], "dependencies": []}, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_rename(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    r = client.patch(f"/api/v1/projects/{p.id}", json={"name": "new"},
                     headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_blocks_add_member(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    seed.user("other")
    r = client.post(f"/api/v1/projects/{p.id}/members",
                    json={"username": "other", "role": "viewer"}, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_archived_still_allows_reads(client, seed):
    owner, p, a, b = _archived_project_with_schema(client, seed)
    assert client.get(f"/api/v1/projects/{p.id}/nodes",
                      headers=_auth(seed, owner)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/edges",
                      headers=_auth(seed, owner)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/schemas",
                      headers=_auth(seed, owner)).status_code == 200
    assert client.get(f"/api/v1/projects/{p.id}/graph",
                      headers=_auth(seed, owner)).status_code == 200
