# backend/AGENTS.md

Parent: [../AGENTS.md](../AGENTS.md) — read it first; this doc only covers rules local to `backend/`.

## Purpose

FastAPI service (Python 3.12) providing the watering-tracker API: plant/room CRUD, watering
schedule computation, photo storage, AI plant identification (provider-neutral AI, Perenual,
Wikipedia clients), and Home Assistant notification/webhook integration.

## Ownership

- `app/` — application code (see Local Contracts below for the layering)
- `tests/` — pytest suite, one file per router/service/script, external services mocked with `respx`
- `scripts/` — standalone CLI entry points run via `python -m scripts.<name>`, also used from Docker
- `data/` — runtime SQLite DB + uploaded photos (git-ignored, not source)
- `requirements.txt` / `requirements-dev.txt`, `pytest.ini`

## Local Contracts

- Layering: `routers/` (HTTP endpoints) → `services/` (business logic) → `models/` (ORM) and
  `clients/` (outbound HTTP to the AI provider/Perenual/Wikipedia/Home Assistant)
- `schemas.py` — Pydantic request/response models; `presenters.py` — maps ORM/domain objects to schemas
- `config.py` — env var loading (backed by root `.env`); `db.py` — SQLite engine/session setup
- `scheduler.py` — background job that computes due waterings and triggers HA notifications
- `i18n.py` / `species_names.py` — localized plant/species name lookups
- Every external service (AI provider, Wikipedia, Perenual, Home Assistant) must stay mocked in tests
  (`respx`) so `pytest -q` runs fully offline without real API keys
- Two `AiVisionClient` instances are wired in `app.main`: `ai_client` (species ID/care data,
  `AI_MODEL`) and `diagnose_ai_client` (plant issue diagnosis, `AI_DIAGNOSE_MODEL`) — kept
  separate so each model/deployment's circuit breaker is independent and a different/stronger
  model can be used for diagnosis without affecting routine identification

## Work Guidance

```bash
cd backend
python3 -m venv .venv          # first time only
source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env     # first time only, then fill in real secrets
```

- Run the dev server: `uvicorn app.asgi:app --reload --port 8080`
- New scripts go in `scripts/`, are invoked as `python -m scripts.<name>`, and need a matching
  test in `tests/test_<name>_script.py`
- New routers/services need corresponding tests mocking any outbound HTTP calls

## Verification

```bash
pytest -q               # unit tests
pytest --cov=app -q     # with coverage
```

## Child DOX Index

- No child AGENTS.md files needed — `app/`, `tests/`, and `scripts/` are cohesive enough to
  stay covered by this single doc.
