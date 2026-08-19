# Droplet 💧

Self-hosted plant watering tracker and reminder app. Snap a photo of a new plant and Droplet
identifies the species (AI + Perenual), works out a sensible watering interval, and reminds
you — with actionable push notifications, if you wire it up to Home Assistant — when it's
time to water again.

Single Docker container, SQLite storage, no cloud account required (besides an AI API key
for photo identification).

## Features

- **Plants grouped by room**, with a one-tap "watered" button per plant or per whole room
- **Add-a-plant photo flow**: upload/take a photo, Droplet asks an AI vision model to identify
  the species, cross-checks [Perenual](https://perenual.com/docs/api) for care data, and falls
  back to sane defaults — you confirm or edit before saving
- **Per-plant watering interval**, editable at any time; interval nudges itself with the
  season (configurable northern/southern hemisphere)
- **Undo** the last watering action
- **Snooze** a reminder (by days or minutes) or set the whole household to **away mode** to
  pause every reminder for a while
- **Push notifications via Home Assistant** (optional): actionable "Watered" / "Snooze" / "Away"
  buttons on your phone, quiet hours, and twice-daily escalation for overdue plants
- **Multi-language** notifications and AI-suggested plant names (English / Hungarian today)
- Installable as a **mobile home-screen app** (manifest + icons), with a wake lock while adding
  plants so the screen doesn't sleep mid-photo
- Nightly **backups** and **orphaned-photo cleanup** scripts, a `/api/health` endpoint, and a
  manual **plant-seeding** script for bootstrapping data without the AI flow

## How it works (architecture)

```
backend/    FastAPI service (Python 3.12), SQLite persistence, pytest test suite
frontend/   Plain TypeScript + Vite SPA (no framework), vitest test suite
docker-compose.yml, Dockerfile   single image: builds the SPA, serves it + the API together
.env.example   full list of configuration variables
```

The Docker image builds the frontend and serves the compiled static files directly from
FastAPI (`StaticFiles` mounted at `/`), so one container serves both the API and the UI — no
separate nginx/reverse proxy needed.

For AI coding agents working in this repo, see [AGENTS.md](AGENTS.md) (and the child
`AGENTS.md` files in [backend/](backend/AGENTS.md) and [frontend/](frontend/AGENTS.md)) for the
project's contribution rules and per-area guidance — not needed for normal human usage.

## Requirements

- Docker + Docker Compose (recommended way to run it), **or** Python 3.12 and Node.js 22 for
  local development without Docker
- An API key for an AI endpoint that supports image input and JSON responses
  (see `AI_API_STYLE` / `AI_BASE_URL` / `AI_MODEL` below) for plant identification
- Optional: a free [Perenual](https://perenual.com/docs/api) API key for better watering-interval data
- Optional: a [Home Assistant](https://www.home-assistant.io/) instance for push notifications

## Quick start (Docker Compose)

```bash
git clone <this-repo-url> droplet
cd droplet
cp .env.example .env
nano .env                 # fill in the required secrets — see "Configuration" below
docker compose up -d --build
curl http://localhost:8080/api/health   # {"status":"ok", ...}
```

Open `http://<host>:8080/` in a browser (or add it to your phone's home screen) and start
adding plants.

The app listens on port `8080` by default; edit the `ports:` mapping in
[docker-compose.yml](docker-compose.yml) to change it. Data (SQLite DB + uploaded photos) is
kept in the `droplet-data` named Docker volume, so `docker compose up -d --build` (rebuilding
after a code change) never loses data.

## Configuration

All configuration lives in `.env` (copy it from `.env.example`, which documents every
variable inline). `.env` is git-ignored and must never be committed — it holds real secrets.

| Variable | Required | Description |
| --- | --- | --- |
| `AI_API_KEY` | yes | API key for the AI endpoint used to identify plants from photos |
| `HA_BASE_URL` | yes* | Base URL of your Home Assistant instance, e.g. `http://192.168.1.50:8123` |
| `HA_LONG_LIVED_TOKEN` | yes* | HA profile → Long-Lived Access Tokens → Create Token |
| `HA_WEBHOOK_SECRET` | yes* | Any random string you generate (`openssl rand -hex 32`); shared between this app and the HA automation that calls it back |
| `AI_API_STYLE` | no | `openai` for `/chat/completions` style APIs, or `azure-openai` for deployment-style endpoints |
| `AI_BASE_URL` | no | Base URL of the AI endpoint, e.g. `https://api.openai.com/v1` or your provider's Azure-style base |
| `AI_MODEL` | no | Model name (`openai`) or deployment name (`azure-openai`) used for identification |
| `AI_API_VERSION` | no | API version string used when `AI_API_STYLE=azure-openai` |
| `AI_DIAGNOSE_MODEL` | no | Optional stronger model/deployment used only for plant-issue diagnosis |
| `PERENUAL_API_KEY` | no | Optional Perenual API key for richer care data; leave blank to skip straight to AI + defaults |
| `APP_PUBLIC_URL` | no | The URL this app is reachable at, e.g. `http://192.168.1.20:8080` — used in notification links |
| `DB_PATH` | no | Path to the SQLite database file (default `data/droplet.sqlite3`) |
| `PHOTOS_DIR` | no | Path to the uploaded-photos directory (default `data/photos`) |
| `NOTIFY_TARGETS` | no | Comma-separated HA `notify.mobile_app_*` suffixes to send reminders to, e.g. `mobile_app_phone1,mobile_app_phone2`. Leave blank to disable push notifications entirely |
| `TIMEZONE` | no | IANA timezone name (e.g. `Europe/Budapest`), used for quiet hours and the twice-daily overdue reminders. Defaults to UTC |
| `QUIET_HOURS_START` / `QUIET_HOURS_END` | no | Hour range (0-23) during which notifications are suppressed. Defaults `22`–`8` |
| `HEMISPHERE` | no | `northern` or `southern` — used to nudge watering intervals with the seasons |
| `LANGUAGE` | no | `en` or `hu` — language for notifications and AI-suggested plant names |

\* `HA_BASE_URL`, `HA_LONG_LIVED_TOKEN`, and `HA_WEBHOOK_SECRET` must be set to *something*
for the app to start (they're required settings), but Home Assistant integration itself is
optional: if you don't use HA, put in any placeholder values, leave `NOTIFY_TARGETS` blank,
and the app runs fine — you just won't get push notifications (the UI still shows what's due).

## Using the app

- **Add a plant**: tap the add button, take/upload a photo, review the AI's species guess
  (or search/enter one manually), confirm the room and watering interval, save
- **Water a plant**: tap the water-drop button on a plant card; tap the room's button to water
  every plant in that room at once
- **Undo**: a toast appears right after watering with an undo option
- **Adjust the schedule**: open a plant's detail view to change its watering interval or reset
  it back to the species default
- **Snooze / away**: snooze an individual plant's next reminder, or set the whole app to away
  mode to pause every reminder while you're travelling
- **Push notifications** (if Home Assistant is configured): reminders arrive as actionable
  notifications with "Watered" / "Snooze 1 day" / "Away 3 days" buttons that update Droplet
  without opening the app

## Home Assistant integration (optional)

Droplet only ever talks to HA for two things: sending actionable notifications, and receiving
the button-press callback. Add this to HA's `configuration.yaml` (or a package file) once the
app is deployed and `HA_WEBHOOK_SECRET` is set, replacing the URL with your own `APP_PUBLIC_URL`:

```yaml
# Forwards "Watered" / "Snooze 1 day" / "Away 3 days" button presses back to the app.
#
# mode: queued (not the default "single") matters here: the HA companion app can
# fire mobile_app_notification_action more than once in quick succession for a
# single button tap (observed ~1-3s apart). With the default "single" mode, any
# trigger that arrives while the rest_command from a previous trigger is still
# in flight is silently *dropped*, not queued — so some button presses appear to
# do nothing even though the automation "triggered" fine in the logbook.
automation:
  - alias: "Droplet: forward notification action"
    mode: queued
    max: 10
    trigger:
      - platform: event
        event_type: mobile_app_notification_action
    action:
      - service: rest_command.droplet_ha_action
        data:
          action: "{{ trigger.event.data.action }}"
          # Some companion-app action payloads omit `tag` (or shape it
          # differently), so default to empty instead of failing template render.
          tag: "{{ trigger.event.data.tag | default('') }}"

rest_command:
  droplet_ha_action:
    url: "http://<your-droplet-host>:8080/api/ha/action"   # match APP_PUBLIC_URL
    method: POST
    headers:
      X-Webhook-Secret: "the same value as HA_WEBHOOK_SECRET in .env"
      Content-Type: "application/json"
    # IMPORTANT: template from service-call variables (`action`, `tag`) rather
    # than from `trigger.*` directly. In HA, rest_command templates are more
    # reliable when the automation passes explicit `data` variables.
    payload: '{"action": "{{ action }}", "tag": "{{ tag }}"}'
```

Optional dashboard shortcut button:

```yaml
type: button
name: Droplet
icon: mdi:flower
tap_action:
  action: url
  url_path: http://<your-droplet-host>:8080/
```

Optional heartbeat (a pull-based REST sensor, since `/api/health` already exists):

```yaml
binary_sensor:
  - platform: rest
    name: Droplet
    resource: http://<your-droplet-host>:8080/api/health
    value_template: "{{ value_json.status == 'ok' }}"
    # Piggyback the HA notify-call failure signal onto the same poll instead
    # of adding a second REST sensor/HTTP round trip.
    json_attributes:
      - last_notification_error
      - last_notification_error_at
    scan_interval: 300

automation:
  - alias: "Droplet: app unreachable alert"
    trigger:
      # A failed request makes the rest platform's binary_sensor go "unavailable",
      # not "off" — so a plain `to: "off"` trigger never fires when the app is
      # actually down. Match anything that isn't "on" instead.
      - platform: template
        value_template: "{{ states('binary_sensor.droplet') != 'on' }}"
        for: "02:00:00"
    action:
      - service: notify.mobile_app_phone1
        data:
          message: "Droplet has been unreachable for 2 hours."

  - alias: "Droplet: notification delivery failing"
    # Covers the case the app itself is fine (binary_sensor.droplet is "on")
    # but its outbound calls to HA's notify service are failing — e.g. a
    # revoked/expired HA_LONG_LIVED_TOKEN.
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('binary_sensor.droplet', 'last_notification_error') not in [None, ''] }}
        for: "00:10:00"
    action:
      - service: notify.mobile_app_phone1
        data:
          message: >
            Droplet reminders may not be reaching your phone
            ({{ state_attr('binary_sensor.droplet', 'last_notification_error') }},
            since {{ state_attr('binary_sensor.droplet', 'last_notification_error_at') }}).
```

## Updating the app

There's no auto-update mechanism — updates are manual, by design, for a single-instance
self-hosted app:

1. Pull/edit the code in place wherever you deployed it.
2. Rebuild and restart the container so the change is picked up:
   ```bash
   docker compose up -d --build
   curl http://localhost:8080/api/health   # {"status":"ok"}
   ```
   A plain `docker compose restart` is **not** enough — the Dockerfile `COPY`s the backend/
   frontend source into the image at build time (no bind-mount for live code), so it just
   restarts the old image unchanged. `--build` is required for code changes to take effect.
3. Data is untouched by rebuilds: the SQLite DB and photos live in the `droplet-data` named
   volume (see `docker-compose.yml`), not in the image, so rebuilding/recreating the container
   never loses data. Back up first anyway if the change is risky (see "Backups" below).

## Backups

```bash
docker compose exec droplet python -m scripts.backup --backup-dir /backups/droplet --keep 14
```

`/backups/droplet` is bind-mounted to `./backups` on the host (see `docker-compose.yml`), so
archives land directly on the host filesystem for whatever backup/offsite-sync job you already
run. Uses SQLite's online backup API (safe to run while the app is up) and tars the DB + photos
folder into `droplet-backup-<timestamp>.tar.gz`, pruning to the most recent `--keep` archives.
Schedule nightly via cron on the host:

```
0 3 * * * cd /path/to/droplet && docker compose exec -T droplet python -m scripts.backup --backup-dir /backups/droplet --keep 14
```

Local development (outside Docker, using the venv):

```bash
cd backend
source .venv/bin/activate
python -m scripts.backup --backup-dir /tmp/droplet-backups --keep 14
```

## Orphaned photo cleanup

`/api/identify` saves the uploaded photo right away, before the user has picked a candidate
and confirmed the add-plant flow. If they abandon that flow, the file is never referenced by a
plant and just sits there. This script deletes unreferenced photos — but only once they're
older than `--min-age-hours` (default 24h), so a photo from a flow that's still in progress (or
just paused) is never touched.

```bash
docker compose exec droplet python -m scripts.cleanup_orphan_photos
```

Add `--dry-run` to see what would be deleted without deleting it. Schedule it alongside the
nightly backup via cron:

```
30 3 * * * cd /path/to/droplet && docker compose exec -T droplet python -m scripts.cleanup_orphan_photos
```

Local development (outside Docker, using the venv):

```bash
cd backend
source .venv/bin/activate
python -m scripts.cleanup_orphan_photos --dry-run
```

## Manual plant seeding

Useful for bootstrapping data before the AI identification flow is wired up with real keys:

```bash
docker compose exec droplet python -m scripts.seed_plant --nickname "Basil" --room "Kitchen" \
  --species "Sweet basil" --interval-days 4 --photo photos/basil.jpg
```

Local development (outside Docker, using the venv):

```bash
cd backend
source .venv/bin/activate
python -m scripts.seed_plant --nickname "Basil" --room "Kitchen" \
  --species "Sweet basil" --interval-days 4 --photo photos/basil.jpg
```

## Local development

Backend (FastAPI):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env   # fill in real secrets, see "Configuration" above
pytest -q
uvicorn app.asgi:app --reload --port 8080
```

Frontend (Vite + TypeScript):

```bash
cd frontend
npm install
npm run dev            # Vite dev server on :5173, proxies /api to localhost:8080
npm test               # vitest unit tests (pure logic + DOM rendering via happy-dom)
npm run build          # production build -> dist/, copied into the Docker image
```

## Testing

```bash
cd backend
source .venv/bin/activate
pytest -q                 # unit tests
pytest --cov=app -q       # with coverage
```

External services (AI provider, Wikipedia, Perenual, Home Assistant) are mocked in tests
(`respx`) so the full suite runs offline without real API keys.

For a fast manual notification/snooze smoke test on a live deployment, you can use a 1-minute
snooze window:

```bash
curl -X POST http://<host>:8080/api/plants/<plant-id>/snooze \
  -H 'Content-Type: application/json' \
  -d '{"minutes": 1}'
```
