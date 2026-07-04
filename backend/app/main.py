from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, auth, cards, integrations, placeholders, research, system, walls, wechat_assistant, ws
from app.core.config import get_settings
from app.db import SessionLocal, create_all
from app.db_migrations import apply_startup_migrations
from app.integrations.wechat_assistant.background import wechat_assistant_background
from app.integrations.wechat_assistant.provider import configure_default_provider
from app.services.seed import seed_database


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_default_provider()
    create_all()
    apply_startup_migrations()
    with SessionLocal() as db:
        seed_database(db)
    wechat_assistant_background.start()
    try:
        yield
    finally:
        wechat_assistant_background.stop()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(walls.router, prefix=settings.api_prefix)
    app.include_router(ai.router, prefix=settings.api_prefix)
    app.include_router(research.router, prefix=settings.api_prefix)
    app.include_router(placeholders.router, prefix=settings.api_prefix)
    app.include_router(cards.router, prefix=settings.api_prefix)
    app.include_router(system.router, prefix=settings.api_prefix)
    app.include_router(integrations.router, prefix=settings.api_prefix)
    app.include_router(wechat_assistant.router, prefix=settings.api_prefix)
    app.include_router(ws.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
