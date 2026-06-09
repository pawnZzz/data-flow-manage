def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_archive_then_unarchive_roundtrip(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    assert client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner)).status_code == 204
    r = client.post(f"/api/v1/projects/{p.id}/unarchive", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert client.post(f"/api/v1/projects/{p.id}/schemas",
                       json={"type_key": "t", "display_name": "T", "fields": []},
                       headers=_auth(seed, owner)).status_code == 201


def test_unarchive_non_archived_409(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/unarchive", headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ARCHIVED"


def test_purge_active_requires_archived_first(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, owner))
    assert r.status_code == 409
    assert r.json()["error"]["details"].get("code") == "PROJECT_NOT_ARCHIVED"


def test_purge_cleans_neo4j_and_mysql(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    a = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    b = client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "b", "type": "t"},
                    headers=_auth(seed, owner)).json()["id"]
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": a, "target_id": b}, headers=_auth(seed, owner))
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["deleted_nodes"] == 2
    assert r.json()["deleted_schemas"] == 1
    assert client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner)).status_code == 404


def test_purge_requires_owner(client, seed):
    owner = seed.user("owner"); admin = seed.user("admin")
    p = seed.project(owner); seed.member(p, admin, "admin")
    client.delete(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, admin))
    assert r.status_code == 403


def test_purge_retries_from_deleting(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    client.post(f"/api/v1/projects/{p.id}/nodes", json={"name": "a", "type": "t"},
                headers=_auth(seed, owner))
    seed.set_status(p, "deleting")
    r = client.post(f"/api/v1/projects/{p.id}/purge", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["deleted_nodes"] == 1
    assert client.get(f"/api/v1/projects/{p.id}", headers=_auth(seed, owner)).status_code == 404


def test_deleting_hidden_from_list(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    seed.set_status(p, "deleting")
    r = client.get("/api/v1/projects?include_archived=true", headers=_auth(seed, owner))
    assert all(row["id"] != p.id for row in r.json())
