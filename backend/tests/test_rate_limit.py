def test_login_rate_limited(client):
    # 默认限流 5/分钟；第 6 次应返回 429
    payloads = {"username": "ghost", "password": "x"}
    codes = [client.post("/api/v1/auth/login", json=payloads).status_code for _ in range(6)]
    assert codes[-1] == 429
    assert all(c in (401, 429) for c in codes)
