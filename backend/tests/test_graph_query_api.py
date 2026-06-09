def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _setup_chain(client, seed):
    # a -> b -> c -> d 链
    owner = seed.user("owner"); p = seed.project(owner)
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))
    ids = {}
    for nm in ["a", "b", "c", "d"]:
        ids[nm] = client.post(f"/api/v1/projects/{p.id}/nodes",
                              json={"name": nm, "type": "t"},
                              headers=_auth(seed, owner)).json()["id"]
    for s, t in [("a", "b"), ("b", "c"), ("c", "d")]:
        client.post(f"/api/v1/projects/{p.id}/edges",
                    json={"source_id": ids[s], "target_id": ids[t]},
                    headers=_auth(seed, owner))
    return owner, p, ids


def test_upstream_recursive(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['a']}/upstream", headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert {n["name"] for n in body["items"]} == {"b", "c", "d"}


def test_downstream_recursive(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['d']}/downstream", headers=_auth(seed, owner))
    assert {n["name"] for n in r.json()["items"]} == {"a", "b", "c"}


def test_upstream_pagination(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['a']}/upstream?limit=2&offset=0",
                   headers=_auth(seed, owner))
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["limit"] == 2


def test_upstream_missing_node_404(client, seed):
    owner = seed.user("owner"); p = seed.project(owner)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/nope/upstream", headers=_auth(seed, owner))
    assert r.status_code == 404


def test_impact_shape(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/nodes/{ids['b']}/impact", headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    assert {n["name"] for n in body["upstream"]} == {"c", "d"}
    assert {n["name"] for n in body["downstream"]} == {"a"}
    assert body["warnings"]["cycles"] == []


def test_subgraph_centered(client, seed):
    owner, p, ids = _setup_chain(client, seed)  # a->b->c->d
    r = client.get(f"/api/v1/projects/{p.id}/graph?center={ids['b']}&depth=1&direction=both",
                   headers=_auth(seed, owner))
    assert r.status_code == 200
    body = r.json()
    # depth1 both：b 自身 + 上游 c + 下游 a
    assert {n["name"] for n in body["nodes"]} == {"a", "b", "c"}
    assert body["stats"]["has_cycle"] is False


def test_subgraph_full_graph(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/graph", headers=_auth(seed, owner))
    body = r.json()
    assert body["stats"]["node_count"] == 4
    assert body["stats"]["edge_count"] == 3


def test_subgraph_direction_upstream(client, seed):
    owner, p, ids = _setup_chain(client, seed)
    r = client.get(f"/api/v1/projects/{p.id}/graph?center={ids['a']}&depth=15&direction=upstream",
                   headers=_auth(seed, owner))
    # a 的上游 b,c,d + a 自身
    assert {n["name"] for n in r.json()["nodes"]} == {"a", "b", "c", "d"}
