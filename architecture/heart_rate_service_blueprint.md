# Event-Aware Garmin Dashboard Blueprint

## Product direction

The service is not just a Garmin dashboard.

It is a personal bio-timeline product that helps a user understand:

- what changed in heart rate, stress, and sleep
- when the change started
- which life events or people were nearby
- which event types repeatedly correlate with better or worse states

## MVP scope

### Data sources

- Garmin account
  - wellness heart rate
  - high-resolution activity heart rate
  - stress
  - sleep
- Manual event journal
- Future: Google Calendar

### Core jobs

1. Connect Garmin with ID/PW for internal testing
2. Backfill a bounded date range
3. Incrementally sync new wellness and activity data
4. Let users write or edit events
5. Detect anomalies and change points
6. Link events to metric segments
7. Render an event-aware dashboard and insight feed

## Architecture choices

### Why the provider boundary matters

Garmin integration should be the only piece that knows whether the service is
using:

- `python-garminconnect` with ID/PW
- or official Garmin OAuth and APIs later

Everything else should consume normalized domain records.

### Data ownership

- Raw provider payloads are optional archival data.
- The database of record should store product-oriented normalized tables.
- Insights should be persisted so the UI does not need to recompute expensive
  analysis on every page load.

## Analysis pipeline

### Stage 1: baseline summaries

- daily resting / average / max heart rate
- intraday hourly heart rate profile
- daily stress summary
- daily sleep summary
- per-activity high-resolution heart rate summaries

### Stage 2: anomaly detection

- elevated resting heart rate
- unusual daytime stress peaks
- abnormally low or short sleep
- unusually high post-event heart rate persistence

### Stage 3: change-point detection

- detect persistent level shifts
- detect changed variability patterns
- detect repeated evening or morning drift

### Stage 4: event attribution

- overlap events with anomaly windows
- score relevance of nearby events
- accumulate evidence by tag, person, and time-of-day

### Stage 5: insight generation

Examples:

- "Work meeting events were followed by higher afternoon stress."
- "Running improved same-day evening stress on average."
- "Sleep quality dropped after late-night calendar events."

## Suggested development order

1. Implement database schema
2. Implement `GarminProvider` boundary
3. Implement unofficial provider
4. Implement sync jobs for heart rate, stress, sleep, and activities
5. Implement event journal CRUD
6. Implement timeline and overview APIs
7. Implement anomaly and change-point tables plus background recompute
8. Add Google Calendar provider
9. Add official Garmin provider when approved
