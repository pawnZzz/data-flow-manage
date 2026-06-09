def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _setup(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    ids = {}
    for nm in ["a", "b", "c"]:
        ids[nm] = client.post(f"/api/v1/projects/{p.id}/nodes",
                              json={"name": nm, "type": "t"},
                              headers=_auth(seed, owner)).json()["id"]
    return owner, p, ids


def _edge(client, seed, p, owner, s, t):
    return client.post(f"/api/v1/projects/{p.id}/edges",
                       json={"source_id": s, "target_id": t}, headers=_auth(seed, owner))


def test_creating_cycle_warns(client, seed):
    owner, p, ids = _setup(client, seed)
    _edge(client, seed, p, owner, ids["a"], ids["b"])
    _edge(client, seed, p, owner, ids["b"], ids["c"])
    # c -> a 制造环
    r = _edge(client, seed, p, owner, ids["c"], ids["a"])
    assert r.status_code == 201
    assert r.json()["warnings"]["creates_cycle"] is True


def test_cycles_endpoint_lists_cycle(client, seed):
    owner, p, ids = _setup(client, seed)
    _edge(client, seed, p, owner, ids["a"], ids["b"])
    _edge(client, seed, p, owner, ids["b"], ids["a"])
    r = client.get(f"/api/v1/projects/{p.id}/cycles", headers=_auth(seed, owner))
    assert r.status_code == 200
    assert len(r.json()) >= 1
    names = {n["name"] for cyc in r.json() for n in cyc["nodes"]}
    assert {"a", "b"} <= names


def test_no_cycle_empty(client, seed):
    owner, p, ids = _setup(client, seed)
    _edge(client, seed, p, owner, ids["a"], ids["b"])
    r = client.get(f"/api/v1/projects/{p.id}/cycles", headers=_auth(seed, owner))
    assert r.json() == []
