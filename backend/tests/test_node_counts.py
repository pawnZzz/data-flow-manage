def _auth(seed, user):
    return {"Authorization": f"Bearer {seed.token(user)}"}


def _mk_schema(client, seed, p, owner):
    client.post(f"/api/v1/projects/{p.id}/schemas",
                json={"type_key": "t", "display_name": "T", "fields": []},
                headers=_auth(seed, owner))


def _mk_node(client, seed, p, owner, name):
    return client.post(f"/api/v1/projects/{p.id}/nodes",
                       json={"name": name, "type": "t"},
                       headers=_auth(seed, owner)).json()["id"]


def _edge(client, seed, p, owner, s, t):
    client.post(f"/api/v1/projects/{p.id}/edges",
                json={"source_id": s, "target_id": t}, headers=_auth(seed, owner))


def test_detail_counts_are_recursive(client, seed):
    # a -> b -> c：a 的上游递归=2（b,c），c 的下游递归=2（a,b）
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    c = _mk_node(client, seed, p, owner, "c")
    _edge(client, seed, p, owner, a, b)
    _edge(client, seed, p, owner, b, c)
    da = client.get(f"/api/v1/projects/{p.id}/nodes/{a}", headers=_auth(seed, owner)).json()
    assert da["upstream_count"] == 2
    assert da["downstream_count"] == 0
    dc = client.get(f"/api/v1/projects/{p.id}/nodes/{c}", headers=_auth(seed, owner)).json()
    assert dc["downstream_count"] == 2
    assert dc["upstream_count"] == 0


def test_list_counts_are_neighbors(client, seed):
    # a -> b -> c：list 里 a 上游邻居=1（仅 b），c 下游邻居=1（仅 b）
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    c = _mk_node(client, seed, p, owner, "c")
    _edge(client, seed, p, owner, a, b)
    _edge(client, seed, p, owner, b, c)
    rows = client.get(f"/api/v1/projects/{p.id}/nodes", headers=_auth(seed, owner)).json()
    by = {n["name"]: n for n in rows}
    assert by["a"]["upstream_count"] == 1 and by["a"]["downstream_count"] == 0
    assert by["b"]["upstream_count"] == 1 and by["b"]["downstream_count"] == 1
    assert by["c"]["upstream_count"] == 0 and by["c"]["downstream_count"] == 1


def test_detail_recursive_dedup_diamond(client, seed):
    # 钻石：a->b->d, a->c->d。d 的下游递归应去重为 3（a,b,c），而非按路径计 4
    owner = seed.user("owner"); p = seed.project(owner); _mk_schema(client, seed, p, owner)
    a = _mk_node(client, seed, p, owner, "a")
    b = _mk_node(client, seed, p, owner, "b")
    c = _mk_node(client, seed, p, owner, "c")
    d = _mk_node(client, seed, p, owner, "d")
    _edge(client, seed, p, owner, a, b)
    _edge(client, seed, p, owner, a, c)
    _edge(client, seed, p, owner, b, d)
    _edge(client, seed, p, owner, c, d)
    dd = client.get(f"/api/v1/projects/{p.id}/nodes/{d}", headers=_auth(seed, owner)).json()
    assert dd["downstream_count"] == 3  # a,b,c 去重
    da = client.get(f"/api/v1/projects/{p.id}/nodes/{a}", headers=_auth(seed, owner)).json()
    assert da["upstream_count"] == 3  # b,c,d 去重
