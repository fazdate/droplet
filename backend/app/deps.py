"""FastAPI dependency providers."""

from collections.abc import Iterator

import httpx
from fastapi import Request
from sqlalchemy.orm import Session

from app.clients.ai import AiVisionClient
from app.clients.perenual import PerenualClient
from app.config import Settings


def get_db(request: Request) -> Iterator[Session]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_ai_client(request: Request) -> AiVisionClient:
    return request.app.state.ai_client


def get_diagnose_ai_client(request: Request) -> AiVisionClient:
    """Separate AI client instance pointed at Settings.ai_diagnose_model.

    Diagnosis can use a different/stronger model than routine identification
    without one model's circuit breaker affecting the other.
    """
    return request.app.state.diagnose_ai_client


def get_perenual_client(request: Request) -> PerenualClient:
    return request.app.state.perenual_client


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Shared, connection-pooled client (see app.main) used by callers, such
    as the species router, that need to pass it through to functions like
    ``fetch_reference_image_url`` rather than construct a client per call."""
    return request.app.state.http_client
