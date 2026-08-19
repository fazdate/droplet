"""FastAPI application factory."""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.clients.ai import AiVisionClient
from app.clients.perenual import PerenualClient
from app.config import Settings
from app.db import create_db_engine, init_db
from app.deps import get_db
from app.routers.notifications import router as notifications_router
from app.routers.photos import router as photos_router
from app.routers.plants import router as plants_router
from app.routers.rooms import router as rooms_router
from app.routers.species import router as species_router
from app.rate_limit import limiter
from app.services.settings_store import get_last_notification_error

health_router = APIRouter()


@health_router.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    # last_notification_error/_at surface HA notify-call failures (e.g. an
    # expired long-lived token) that the scheduler tick would otherwise only
    # log — see TODO.md section 6. Piggybacks on this existing REST resource
    # so the HA heartbeat sensor's poll can drive a second template sensor
    # without an extra HTTP round trip.
    error = get_last_notification_error(db)
    return {
        "status": "ok",
        "last_notification_error": error["message"] if error else None,
        "last_notification_error_at": error["at"] if error else None,
    }


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    await app.state.http_client.aclose()


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    static_dir: Path | str | None = None,
    ai_client: AiVisionClient | None = None,
    diagnose_ai_client: AiVisionClient | None = None,
    perenual_client: PerenualClient | None = None,
) -> FastAPI:
    settings = settings or Settings()
    engine = engine or create_db_engine(f"sqlite:///{settings.db_path}")
    init_db(engine)
    limiter.reset()

    app = FastAPI(title="Droplet", lifespan=_lifespan)
    app.state.settings = settings
    app.state.session_factory = _session_factory(engine)
    app.state.undo_store = {}
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    # One pooled, keep-alive client shared by AI/Perenual/Wikipedia calls
    # (see app.deps.get_http_client) instead of each call paying a fresh
    # TCP/TLS handshake — see TODO.md "Speed up plant identification".
    app.state.http_client = httpx.AsyncClient()
    app.state.ai_client = ai_client or AiVisionClient(
        api_style=settings.ai_api_style,
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        api_version=settings.ai_api_version,
        http_client=app.state.http_client,
    )
    # A second client instance for the (optionally different/stronger) model
    # used by the plant-issue-diagnosis feature — shares the same pooled
    # http_client but keeps its own circuit breaker.
    app.state.diagnose_ai_client = diagnose_ai_client or AiVisionClient(
        api_style=settings.ai_api_style,
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_diagnose_model,
        api_version=settings.ai_api_version,
        http_client=app.state.http_client,
    )
    app.state.perenual_client = perenual_client or PerenualClient(
        api_key=settings.perenual_api_key, http_client=app.state.http_client
    )

    # API routes are registered first so they take priority over the catch-all
    # static mount below (Starlette matches routes in registration order).
    app.include_router(health_router)
    app.include_router(rooms_router)
    app.include_router(plants_router)
    app.include_router(notifications_router)
    app.include_router(species_router)
    # Must be registered before the "/photos" StaticFiles mount below so
    # /photos/thumbnails/* hits the lazy-thumbnail route instead of falling
    # through to a (likely 404) static file lookup — see app.routers.photos.
    app.include_router(photos_router)

    # Serve uploaded plant photos (plan section 4.4) — must be registered
    # before the catch-all "/" static mount below so it isn't shadowed.
    photos_path = Path(settings.photos_dir)
    photos_path.mkdir(parents=True, exist_ok=True)
    app.mount("/photos", StaticFiles(directory=photos_path), name="photos")

    static_path = Path(static_dir) if static_dir is not None else Path("static")
    if static_path.is_dir():
        app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

    return app


def _session_factory(engine: Engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine)
