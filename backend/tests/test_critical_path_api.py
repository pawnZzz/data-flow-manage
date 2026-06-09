def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _chain(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    ids = {}
    for nm in ["a", "b", "c"]:
        ids[nm] = client.post(f"/api/v1/projects/{p.id}/nodes",
                              json={"name": nm, "type": "t"},
                              headers=_auth(seed, owner)).json()["id"]
    for s, t in [("a", "b"), ("b", "c")]:
        client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": ids[s], "target_id": ids[t]},
                    headers=_auth(seed, owner))
    return owner, p, ids


def test_critical_impact_mode(client, seed):
    owner, p, ids = _chain(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "impact"}, headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "impact"
    assert len(body["paths"]) == 1
    assert body["paths"][0]["depth"] >= 1


def test_critical_longest_mode(client, seed):
    owner, p, ids = _chain(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "longest"}, headers=_auth(seed, owner))
    assert r.status_code == 200
    # 最长链 a->b->c depth=2
    assert max(pth["depth"] for pth in r.json()["paths"]) == 2


def test_critical_manual_mode_with_node_ids(client, seed):
    owner, p, ids = _chain(client, seed)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "manual", "node_ids": [ids["a"], ids["c"]]},
                    headers=_auth(seed, owner))
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert len(paths) == 1
    assert {n["name"] for n in paths[0]["nodes"]} == {"a", "b", "c"}


def test_critical_invalid_mode_422(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.post(f"/api/v1/projects/{p.id}/critical-paths",
                    json={"mode": "bogus"}, headers=_auth(seed, owner))
    assert r.status_code == 422
