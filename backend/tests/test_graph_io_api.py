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
