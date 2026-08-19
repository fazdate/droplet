# frontend/AGENTS.md

Parent: [../AGENTS.md](../AGENTS.md) — read it first; this doc only covers rules local to `frontend/`.

## Purpose

Plain TypeScript + Vite single-page app for the watering tracker UI: browsing plants/rooms,
the add-plant flow (photo capture + AI identification), watering cadence editing, and
notification/toast handling. No frontend framework — hand-written DOM rendering.

## Ownership

- `src/` — application code (see Local Contracts below)
- `tests/` — vitest suite (one file per `src/` module), DOM tests use `happy-dom`
- `public/` — static assets (favicon, manifest, icon sprite) served as-is
- `index.html`, `vite.config.ts`, `vitest.config.ts`, `tsconfig.json`

## Local Contracts

- `api.ts` — the only module allowed to call the backend `/api/*` endpoints; other modules
  must go through it rather than calling `fetch` directly
- `render.ts` — renders plant/room lists and detail views into the DOM
- `addPlantFlow.ts` / `addPlantUi.ts` — the add-plant wizard (photo → AI identify → confirm);
  keep flow/state logic in `addPlantFlow.ts` and DOM wiring in `addPlantUi.ts`
- `cadenceEditor.ts` — watering interval editing UI; `careInfo.ts` — plant care info display
- `imageResize.ts` — client-side photo resize before upload (keeps uploads small)
- `wakeLock.ts` — Screen Wake Lock API wrapper; `i18n.ts` — UI string localization
- `format.ts` — shared date/number formatting helpers; `toast.ts` — transient UI notifications
- Every module in `src/` should have a matching test file in `tests/`
- `style.css` defines the design system as CSS custom properties on `:root` (colors, spacing,
  radius, type scale) with a `prefers-color-scheme: dark` override block — never hardcode hex
  colors or one-off spacing/radius values in new rules; add or reuse a `--color-*`/`--space-*`/
  `--radius-*`/`--font-size-*` token instead

## Work Guidance

```bash
cd frontend
npm install        # first time / after dependency changes
npm run dev        # Vite dev server on :5173, proxies /api to localhost:8080
npm run build      # production build -> dist/, copied into the Docker image
```

## Verification

```bash
npm test              # vitest run
npm run test:coverage  # with coverage
```

## Child DOX Index

- No child AGENTS.md files needed — `src/`, `tests/`, and `public/` are cohesive enough to
  stay covered by this single doc.
