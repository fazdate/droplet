# DOX framework

- DOX is the AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Core Contract

- AGENTS.md files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable AGENTS.md plus every parent AGENTS.md above it

## Read Before Editing

1. Read this root AGENTS.md
2. If [AGENTS.local.md](AGENTS.local.md) exists at the repo root, read it too — it holds this
   deployment's personal/environment-specific details (git-ignored, never pushed) and takes
   precedence over this file for anything specific to the current machine
3. Identify every file or folder you expect to touch
4. Walk from the repository root to each target path
5. Read every AGENTS.md found along each route
6. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the path, read that child and continue from there
7. Use the nearest AGENTS.md as the local contract and parent docs for repo-wide rules
8. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Hierarchy

- Root AGENTS.md (this file) is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:
- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

---

# Droplet

## Purpose

Self-hosted plant watering tracker + reminder app: FastAPI backend + plain TypeScript/Vite
frontend, single Docker image, with optional Home Assistant integration for actionable
watering-reminder notifications.

## Ownership

- Root: deployment (`Dockerfile`, `docker-compose.yml`), secrets template (`.env.example`),
  human-facing operational docs (`README.md`), this DOX tree
- [backend/](backend/AGENTS.md): FastAPI service, SQLite persistence, scripts, pytest suite
- [frontend/](frontend/AGENTS.md): Vite + TypeScript SPA, vitest suite
- `backups/`: bind-mounted destination for `scripts.backup` archives — generated artifacts, not edited by hand

## Local Contracts

- `.env` holds real secrets and is never committed (see `.gitignore`); `.env.example` is the
  template kept in sync with every required variable
- The Dockerfile `COPY`s backend + frontend source at build time (no live bind-mount for
  code) — the SQLite DB and photos persist separately in the `droplet-data` named volume
- Full deployment steps, Home Assistant YAML, backup/cleanup cron jobs, and manual plant
  seeding are documented in [README.md](README.md) — treat README as the source of truth for
  those procedures instead of duplicating them here
- This file and every other tracked doc must stay generic (no personal IPs, hostnames,
  paths, or other environment-specific details) — that kind of detail belongs in
  [AGENTS.local.md](AGENTS.local.md) (git-ignored) instead

## Work Guidance

- **Local backend dev**: `cd backend && source .venv/bin/activate && uvicorn app.asgi:app --reload --port 8080`
- **Local frontend dev**: `cd frontend && npm run dev` (Vite on :5173, proxies `/api` to :8080)
- **Restart after a code change**: `docker compose up -d --build` — a plain
  `docker compose restart` does **not** pick up code changes (see Local Contracts above);
  `--build` is required every time
- **Health check after restart**: `curl http://localhost:8080/api/health` → `{"status":"ok"}`
- **Before risky changes**: take a backup first — see README "Backups"
- Data (SQLite DB + photos) survives rebuilds; only the named volume holds it, never the image
- This deployment's actual host/path/IP and any personal workflow notes: see
  [AGENTS.local.md](AGENTS.local.md) if present

## Verification

- Backend: `cd backend && pytest -q` (see [backend/AGENTS.md](backend/AGENTS.md))
- Frontend: `cd frontend && npm test` (see [frontend/AGENTS.md](frontend/AGENTS.md))

## User Preferences

(none recorded yet — add durable behavior preferences here as they come up)

## Child DOX Index

- [backend/AGENTS.md](backend/AGENTS.md) — FastAPI service: `app/`, `tests/`, `scripts/`
- [frontend/AGENTS.md](frontend/AGENTS.md) — TypeScript/Vite SPA: `src/`, `tests/`
- Root-owned files: `README.md`, `TODO.md`, `Dockerfile`, `docker-compose.yml`,
  `.dockerignore`, `.env.example`, `.gitignore`, `backups/` (generated, not hand-edited)
- `AGENTS.local.md` (git-ignored, optional) — this deployment's personal/environment-specific
  supplement; read it if present, but never add its content here or to any tracked doc
