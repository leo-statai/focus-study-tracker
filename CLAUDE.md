# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Direct (development)
python3 app.py

# Docker (production-like)
docker compose up -d --build
docker compose down
```

App listens on `http://localhost:8000`. No external dependencies — stdlib only.

## Architecture

Everything lives in two places: **`app.py`** (server + API + DB) and **`static/`** (frontend).

### Backend (`app.py`)

A single file using Python's stdlib `http.server.ThreadingHTTPServer`. No framework.

- **`AppHandler`** subclasses `BaseHTTPRequestHandler`, routing manually in `do_GET` / `do_POST` / `do_DELETE`.
- After every mutating operation, the handler calls `state_data()` and returns the full app state to the client — this is the single source of truth for UI updates.
- **`init_db()`** creates the schema on startup and seeds a default project + subjects if none exist.
- **`session_segments()`** is the core accounting function: it clips sessions to period boundaries and splits multi-day sessions at midnight so per-day totals are correct.
- All datetimes are stored as UTC ISO strings in SQLite. Timezone conversion uses `zoneinfo`.

### Timezone handling

The client sends `X-Client-Time-Zone` (IANA name) and `X-Client-Timezone-Offset` (minutes) headers with every request. `request_timezone()` in `app.py` resolves these to a `ZoneInfo` or `timezone` object used for all display-time calculations.

### Database

SQLite at `data/estudos.sqlite` (path configurable via `APP_DB_PATH` env var). Three tables: `projects`, `subjects`, `study_sessions`. Only one project is active at a time. The `data/` directory is git-ignored.

### Frontend (`static/`)

Vanilla JS, no build step. `app.js` holds a single `state` object and calls `renderState()` / `renderReport()` after every API response. Charts (gauge, bar, donut) are drawn directly on `<canvas>` elements. While a session is running, the frontend polls `/api/state` every second to update the live timer.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/state` | Full app state |
| GET | `/api/reports?period=today\|week\|month\|total` | Report for a period |
| POST | `/api/project` | Update project name/goals |
| POST | `/api/subjects` | Create subject |
| POST | `/api/subjects/:id` | Update subject |
| DELETE | `/api/subjects/:id` | Delete subject + its sessions |
| POST | `/api/timer/start` | Start session for a subject |
| POST | `/api/timer/pause` | Close active session |
| POST | `/api/timer/switch` | Atomically close current + open new session |
| POST | `/api/reset` | Wipe DB and reinitialize |

## Crash Recovery / Power-Outage Protection

A background daemon thread (`_checkpoint_loop`) rotates the active session every `CHECKPOINT_INTERVAL` seconds: it closes the current open session and immediately opens a new one for the same subject. This keeps the "unconfirmed" open session in the DB to at most `CHECKPOINT_INTERVAL` seconds.

On startup, `recover_orphaned_sessions()` closes any session still open from a previous crash by setting `ended_at = started_at` (zero duration, not counted in reports). The combination guarantees at most `CHECKPOINT_INTERVAL` seconds of study time can be lost on an ungraceful shutdown.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `APP_DATA_DIR` | `<repo>/data` | Directory for the SQLite file |
| `APP_DB_PATH` | `$APP_DATA_DIR/estudos.sqlite` | Full DB path override |
| `CHECKPOINT_INTERVAL` | `300` | Seconds between session checkpoints (crash data-loss cap) |
