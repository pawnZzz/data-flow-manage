from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="任务血缘管理工具", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
