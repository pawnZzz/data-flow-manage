# 后端（Phase 1：认证）

## 启动依赖

```bash
docker compose up -d mysql neo4j
```

## 安装与初始化

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
```

## 运行

```bash
uvicorn app.main:app --reload
# 健康检查
curl http://localhost:8000/api/v1/health
```

## 测试

需要本机 Docker（testcontainers 会拉起临时 MySQL）：

```bash
pytest -v
```

## 安全注意

生产部署务必在 `.env` 中将 `JWT_SECRET` 设为至少 32 字节的随机串（HS256 要求），不要使用默认占位值。
