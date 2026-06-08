def test_login_rate_limited(client):
    # 默认限流 5/分钟；第 6 次应返回 429
    payloads = {"username": "ghost", "password": "x"}
    codes = [client.post("/api/v1/auth/login", json=payloads).status_code for _ in range(6)]
    assert codes[-1] == 429
    assert all(c in (401, 429) for c in codes)


def test_rate_limit_uses_envelope(client):
    payloads = {"username": "ghost", "password": "x"}
    last = None
    for _ in range(6):
        last = client.post("/api/v1/auth/login", json=payloads)
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "RATE_LIMITED"
