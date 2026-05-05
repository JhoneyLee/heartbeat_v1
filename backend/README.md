## Garmin Event-Aware Dashboard Backend

This directory is a service-oriented scaffold for evolving the current
single-user Garmin analysis project into a multi-account web application.

### Goals

- Keep the Garmin integration swappable.
- Store normalized heart rate, stress, sleep, activity, and event data.
- Support dashboard, anomaly detection, change-point analysis, and insight APIs.

### Layout

- `app/main.py`: FastAPI entrypoint
- `app/config.py`: environment-driven settings
- `app/api/`: HTTP routes
- `app/domain/`: normalized internal data models and provider contract
- `app/providers/`: Garmin provider implementations
- `app/services/`: sync and analysis orchestration
- `sql/schema.sql`: initial PostgreSQL schema draft

### Provider strategy

The important boundary is `GarminProvider`.

- `UnofficialGarminProvider`
  - internal testing
  - Garmin ID/PW
  - `python-garminconnect`
- `OfficialGarminProvider`
  - later production path
  - Garmin OAuth
  - Health API / Activity API

All API routes and services should depend on normalized domain models instead of
raw Garmin response payloads.

### Suggested local run flow

This scaffold already supports a practical local-server phase before any real
deployment.

#### Current local mode

- `dashboard` routes read from the existing project SQLite database:
  - `data/processed/garmin_heart_rate.sqlite3`
- `sync` routes reuse the current collector and analyzer scripts:
  - `scripts/fetch_garmin_heart_rate_fine.py`
  - `scripts/analyze_heart_rate.py`

That means your Mac can act like the backend server during development while
still using the data pipeline that already works today.

#### How to run it locally

1. Create a service virtualenv inside `backend/` or reuse a project env.
2. Install `backend/requirements.txt`.
3. Start the API:

```bash
cd backend
uvicorn app.main:app --reload
```

#### Useful local endpoints

- `GET /app`
- `GET /healthz`
- `GET /api/dashboard/overview?start=2026-04-28&end=2026-05-05`
- `GET /api/dashboard/heart-rate/daily?start=2026-04-28&end=2026-05-05`
- `GET /api/dashboard/heart-rate/hourly?start=2026-04-28&end=2026-05-05`
- `GET /api/dashboard/stress/daily?start=2026-04-28&end=2026-05-05`
- `GET /api/dashboard/sleep/daily?start=2026-04-28&end=2026-05-05`
- `GET /api/dashboard/activities?start=2026-04-28&end=2026-05-05`
- `GET /api/dashboard/activities/{activity_id}/heart-rate`
- `POST /api/sync/garmin`
- `POST /api/sync/garmin/backfill`

#### Next transition

After local validation, the same API shape can be kept while replacing:

- local SQLite with PostgreSQL
- script-based sync with service-layer persistence
- unofficial Garmin login with official OAuth/API
