"""ASGI entrypoint for uvicorn (``uvicorn app.asgi:app``).

Kept separate from ``app.main`` so importing ``app.main`` (e.g. from tests)
never eagerly builds a real ``Settings()``/DB engine from the environment.
"""

import logging

from app.main import create_app
from app.scheduler import build_scheduler

# Without this, the root logger has no handler, so every app.* LOG.info(...)
# call (AI/Perenual/Wikipedia timing + failure diagnostics — see
# TODO.md "Speed up plant identification") is silently dropped: only
# uvicorn's own bare access log line (path + final status, no internal
# timing) is visible. Configured once here, before create_app()/the
# scheduler start logging anything.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = create_app()

_scheduler = build_scheduler(session_factory=app.state.session_factory, settings=app.state.settings)
_scheduler.start()
