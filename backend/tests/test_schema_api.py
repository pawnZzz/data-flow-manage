def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def test_create_and_get_schema(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.post(
        f"/api/v1/projects/{p.id}/schemas",
        json={"type_key": "data_task", "display_name": "数据任务",
              "fields": [{"name": "engine", "label": "引擎", "type": "enum",
                          "options": ["spark"], "required": True}]},
        headers=_auth(seed, owner),
    )
    assert r.status_code == 201
    assert r.json()["type_key"] == "data_task"
    r2 = client.get(f"/api/v1/projects/{p.id}/schemas/data_task", headers=_auth(seed, owner))
    assert r2.status_code == 200
    assert r2.json()["fields"][0]["name"] == "engine"


def test_duplicate_type_key_409(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    body = {"type_key": "t", "display_name": "T", "fields": []}
    client.post(f"/api/v1/projects/{p.id}/schemas", json=body, headers=_auth(seed, owner))
    r = client.post(f"/api/v1/projects/{p.id}/schemas", json=body, headers=_auth(seed, owner))
    assert r.status_code == 409


def test_list_schemas(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    for tk in ["a", "b"]:
        client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": tk, "display_name": tk, "fields": []},
                    headers=_auth(seed, owner))
    r = client.get(f"/api/v1/projects/{p.id}/schemas", headers=_auth(seed, owner))
    assert {s["type_key"] for s in r.json()} == {"a", "b"}


def test_get_missing_schema_404(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    r = client.get(f"/api/v1/projects/{p.id}/schemas/nope", headers=_auth(seed, owner))
    assert r.status_code == 404


def test_update_schema(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    r = client.put(f"/api/v1/projects/{p.id}/schemas/t",
                   json={"display_name": "T2",
                         "fields": [{"name": "sla", "label": "SLA", "type": "string"}]},
                   headers=_auth(seed, owner))
    assert r.status_code == 200
    assert r.json()["display_name"] == "T2"
    assert r.json()["fields"][0]["name"] == "sla"


def test_delete_schema(client, seed):
    owner = seed.user("owner")
    p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    r = client.delete(f"/api/v1/projects/{p.id}/schemas/t", headers=_auth(seed, owner))
    assert r.status_code == 204


def test_schema_write_requires_editor(client, seed):
    owner = seed.user("owner")
    viewer = seed.user("viewer")
    p = seed.project(owner)
    seed.member(p, viewer, "viewer")
    r = client.post(f"/api/v1/projects/{p.id}/schemas",
                    json={"type_key": "t", "display_name": "T", "fields": []},
                    headers=_auth(seed, viewer))
    assert r.status_code == 403


def test_schema_delete_requires_admin(client, seed):
    owner = seed.user("owner")
    editor = seed.user("editor")
    p = seed.project(owner)
    seed.member(p, editor, "editor")
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    r = client.delete(f"/api/v1/projects/{p.id}/schemas/t", headers=_auth(seed, editor))
    assert r.status_code == 403
