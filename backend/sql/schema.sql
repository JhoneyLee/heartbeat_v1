-- Initial PostgreSQL schema draft for the event-aware Garmin dashboard service.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS garmin_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    auth_type TEXT NOT NULL,
    garmin_email TEXT NOT NULL,
    encrypted_secret TEXT,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    last_sync_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS calendar_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_heart_rate_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    calendar_date DATE NOT NULL,
    resting_heart_rate INTEGER,
    min_heart_rate INTEGER,
    max_heart_rate INTEGER,
    average_heart_rate DOUBLE PRECISION,
    sample_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, calendar_date)
);

CREATE TABLE IF NOT EXISTS daily_heart_rate_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    calendar_date DATE NOT NULL,
    timestamp_local TIMESTAMPTZ NOT NULL,
    bpm INTEGER NOT NULL,
    source TEXT NOT NULL,
    UNIQUE (user_id, source, timestamp_local, bpm)
);

CREATE TABLE IF NOT EXISTS daily_stress_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    calendar_date DATE NOT NULL,
    average_stress DOUBLE PRECISION,
    max_stress INTEGER,
    rest_stress_duration_seconds INTEGER,
    UNIQUE (user_id, calendar_date)
);

CREATE TABLE IF NOT EXISTS daily_sleep_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sleep_date DATE NOT NULL,
    sleep_start_local TIMESTAMPTZ,
    sleep_end_local TIMESTAMPTZ,
    total_sleep_seconds INTEGER,
    deep_sleep_seconds INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds INTEGER,
    awake_seconds INTEGER,
    sleep_score INTEGER,
    UNIQUE (user_id, sleep_date)
);

CREATE TABLE IF NOT EXISTS activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider_activity_id TEXT NOT NULL,
    activity_type TEXT,
    activity_name TEXT,
    calendar_date DATE,
    start_time_local TIMESTAMPTZ,
    duration_seconds DOUBLE PRECISION,
    distance_meters DOUBLE PRECISION,
    average_heart_rate DOUBLE PRECISION,
    max_heart_rate INTEGER,
    UNIQUE (user_id, provider_activity_id)
);

CREATE TABLE IF NOT EXISTS activity_heart_rate_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id UUID NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    timestamp_local TIMESTAMPTZ NOT NULL,
    bpm INTEGER NOT NULL,
    UNIQUE (activity_id, timestamp_local, bpm)
);

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    start_time_local TIMESTAMPTZ NOT NULL,
    end_time_local TIMESTAMPTZ,
    location TEXT,
    valence TEXT NOT NULL DEFAULT 'neutral',
    intensity INTEGER NOT NULL DEFAULT 3,
    is_all_day BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    tag TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_people (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric_type TEXT NOT NULL,
    start_time_local TIMESTAMPTZ NOT NULL,
    end_time_local TIMESTAMPTZ,
    score DOUBLE PRECISION NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS change_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric_type TEXT NOT NULL,
    detected_at_local TIMESTAMPTZ NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    direction TEXT,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    insight_type TEXT NOT NULL,
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    headline TEXT NOT NULL,
    explanation TEXT NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_metric_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    linked_object_type TEXT NOT NULL,
    linked_object_id UUID NOT NULL,
    relevance_score DOUBLE PRECISION NOT NULL,
    rationale TEXT
);

CREATE TABLE IF NOT EXISTS sync_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_hr_samples_user_time
    ON daily_heart_rate_samples (user_id, timestamp_local);

CREATE INDEX IF NOT EXISTS idx_activity_hr_samples_activity_time
    ON activity_heart_rate_samples (activity_id, timestamp_local);

CREATE INDEX IF NOT EXISTS idx_events_user_time
    ON events (user_id, start_time_local);

CREATE INDEX IF NOT EXISTS idx_anomalies_user_metric_time
    ON anomalies (user_id, metric_type, start_time_local);

CREATE INDEX IF NOT EXISTS idx_change_points_user_metric_time
    ON change_points (user_id, metric_type, detected_at_local);
