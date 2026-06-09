from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.exceptions import register_exception_handlers
from app.rate_limit import limiter


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.environment == "production" and settings.jwt_secret == "change-me-in-production":
        raise RuntimeError("生产环境必须设置非默认的 JWT_SECRET（≥32 字节）")
    app = FastAPI(title="任务血缘管理工具", version="0.1.0")

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后再试", "details": {}}},
        )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    from app.routers import auth as auth_router

    app.include_router(auth_router.router)

    from app.routers import projects as projects_router

    app.include_router(projects_router.router)

    from app.routers import members as members_router

    app.include_router(members_router.router)

    from app.routers import schemas as schemas_router

    app.include_router(schemas_router.router)

    from app.routers import nodes as nodes_router

    app.include_router(nodes_router.router)

    from app.routers import edges as edges_router

    app.include_router(edges_router.router)

    from app.routers import graph as graph_router

    app.include_router(graph_router.router)

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
