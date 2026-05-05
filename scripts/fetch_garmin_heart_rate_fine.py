#!/usr/bin/env python3
"""Fetch finest-available Garmin heart rate data.

This script stores two different streams:
1. All-day wellness heart rate from Garmin Connect's daily endpoint.
2. Activity heart rate parsed from original activity FIT files for finer detail.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import zipfile
from datetime import date, datetime, timedelta, timezone
from getpass import getpass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fitparse import FitFile
from garminconnect import Garmin

try:
    from garminconnect import ActivityDownloadFormat
except ImportError:
    ActivityDownloadFormat = None  # type: ignore[assignment]


ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_HEART_RATE_DIR = ROOT_DIR / "data" / "raw" / "heart_rate"
RAW_ACTIVITY_DIR = ROOT_DIR / "data" / "raw" / "activities"
DB_PATH = ROOT_DIR / "data" / "processed" / "garmin_heart_rate.sqlite3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch finest-available Garmin heart rate data."
    )
    parser.add_argument("--date", help="Single date in YYYY-MM-DD format.")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of recent days to fetch when no explicit date range is provided.",
    )
    parser.add_argument(
        "--skip-wellness",
        action="store_true",
        help="Skip the daily wellness heart rate endpoint and only fetch activity FIT data.",
    )
    parser.add_argument(
        "--skip-activities",
        action="store_true",
        help="Skip activity FIT downloads and only fetch the daily wellness heart rate endpoint.",
    )
    return parser.parse_args()


def getenv_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_timezone() -> ZoneInfo:
    tz_name = os.getenv("GARMIN_TIMEZONE", "Asia/Seoul")
    return ZoneInfo(tz_name)


def resolve_dates(args: argparse.Namespace, tz: ZoneInfo) -> List[date]:
    if args.date:
        return [date.fromisoformat(args.date)]

    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
        end_date = date.fromisoformat(args.end_date or args.start_date)
        if end_date < start_date:
            raise ValueError("end-date must be on or after start-date")
        total_days = (end_date - start_date).days + 1
        return [start_date + timedelta(days=offset) for offset in range(total_days)]

    today_local = datetime.now(tz).date()
    return [today_local - timedelta(days=offset) for offset in range(args.days)]


def create_client() -> Garmin:
    email = getenv_required("GARMIN_EMAIL")
    password = getenv_required("GARMIN_PASSWORD")
    tokens_dir = os.getenv("GARMIN_TOKENS_DIR", "~/.garminconnect")

    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: getpass("Garmin MFA code: "),
    )
    client.login(tokens_dir)
    return client


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_summary (
            calendar_date TEXT PRIMARY KEY,
            resting_heart_rate INTEGER,
            min_heart_rate INTEGER,
            max_heart_rate INTEGER,
            average_heart_rate REAL,
            sample_count INTEGER NOT NULL,
            raw_file TEXT NOT NULL,
            fetched_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS heart_rate_samples (
            calendar_date TEXT NOT NULL,
            timestamp_utc TEXT NOT NULL,
            timestamp_local TEXT NOT NULL,
            bpm INTEGER NOT NULL,
            raw_file TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'wellness',
            PRIMARY KEY (source, timestamp_utc, bpm)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            activity_id INTEGER PRIMARY KEY,
            activity_name TEXT,
            activity_type TEXT,
            calendar_date TEXT,
            start_time_local TEXT,
            start_time_gmt TEXT,
            duration_seconds REAL,
            distance_meters REAL,
            source_file TEXT NOT NULL,
            fetched_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_heart_rate_samples (
            activity_id INTEGER NOT NULL,
            timestamp_utc TEXT NOT NULL,
            timestamp_local TEXT NOT NULL,
            bpm INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            PRIMARY KEY (activity_id, timestamp_utc, bpm)
        )
        """
    )
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(heart_rate_samples)").fetchall()
    }
    if "source" not in columns:
        conn.execute(
            "ALTER TABLE heart_rate_samples ADD COLUMN source TEXT NOT NULL DEFAULT 'wellness'"
        )
    conn.commit()


def safe_int(value: object) -> Optional[int]:
    if value in (None, "", -1):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def heart_rate_average(samples: Sequence[Tuple[str, int]]) -> Optional[float]:
    if not samples:
        return None
    return round(sum(bpm for _, bpm in samples) / len(samples), 2)


def normalize_wellness_samples(
    heart_rate_values: Optional[Iterable[Sequence[object]]],
    tz: ZoneInfo,
) -> List[Tuple[str, int]]:
    normalized: List[Tuple[str, int]] = []
    if heart_rate_values is None:
        return normalized
    for item in heart_rate_values:
        if not isinstance(item, Sequence) or len(item) < 2:
            continue

        timestamp_ms = item[0]
        bpm = safe_int(item[1])
        if bpm is None or bpm <= 0:
            continue

        try:
            timestamp_seconds = float(timestamp_ms) / 1000
        except (TypeError, ValueError):
            continue

        local_time = datetime.fromtimestamp(
            timestamp_seconds, tz=timezone.utc
        ).astimezone(tz)
        normalized.append((local_time.isoformat(), bpm))

    normalized.sort(key=lambda row: row[0])
    return normalized


def raw_heart_rate_file_path(fetch_date: date) -> Path:
    return RAW_HEART_RATE_DIR / f"{fetch_date.isoformat()}.json"


def save_wellness_json(payload: dict, fetch_date: date) -> Path:
    RAW_HEART_RATE_DIR.mkdir(parents=True, exist_ok=True)
    target = raw_heart_rate_file_path(fetch_date)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def upsert_wellness_day(
    conn: sqlite3.Connection,
    fetch_date: date,
    raw_path: Path,
    payload: dict,
    samples: Sequence[Tuple[str, int]],
) -> None:
    fetched_at_utc = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "DELETE FROM heart_rate_samples WHERE calendar_date = ? AND source = 'wellness'",
        (fetch_date.isoformat(),),
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO heart_rate_samples (
            calendar_date,
            timestamp_utc,
            timestamp_local,
            bpm,
            raw_file,
            source
        ) VALUES (?, ?, ?, ?, ?, 'wellness')
        """,
        [
            (
                fetch_date.isoformat(),
                datetime.fromisoformat(local_iso)
                .astimezone(timezone.utc)
                .isoformat(),
                local_iso,
                bpm,
                str(raw_path),
            )
            for local_iso, bpm in samples
        ],
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO daily_summary (
            calendar_date,
            resting_heart_rate,
            min_heart_rate,
            max_heart_rate,
            average_heart_rate,
            sample_count,
            raw_file,
            fetched_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fetch_date.isoformat(),
            safe_int(payload.get("restingHeartRate")),
            safe_int(payload.get("minHeartRate")),
            safe_int(payload.get("maxHeartRate")),
            heart_rate_average(samples),
            len(samples),
            str(raw_path),
            fetched_at_utc,
        ),
    )
    conn.commit()


def fetch_wellness_for_dates(
    client: Garmin,
    conn: sqlite3.Connection,
    fetch_dates: Sequence[date],
    tz: ZoneInfo,
) -> None:
    for fetch_date in fetch_dates:
        date_text = fetch_date.isoformat()
        print(f"[wellness] fetch {date_text}")
        payload = client.get_heart_rates(date_text)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected Garmin payload for {date_text}: {type(payload)}")

        samples = normalize_wellness_samples(payload.get("heartRateValues", []), tz)
        raw_path = save_wellness_json(payload, fetch_date)
        upsert_wellness_day(conn, fetch_date, raw_path, payload, samples)
        print(
            f"[wellness] saved {date_text} samples={len(samples)} "
            f"resting={safe_int(payload.get('restingHeartRate'))} "
            f"max={safe_int(payload.get('maxHeartRate'))}"
        )


def normalize_activity_rows(result: object) -> List[dict]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        possible_lists = [
            result.get("activities"),
            result.get("items"),
            result.get("results"),
        ]
        for candidate in possible_lists:
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
    return []


def activity_date_matches(activity: dict, fetch_date: date) -> bool:
    candidates = [
        activity.get("startTimeLocal"),
        activity.get("startTimeGMT"),
        activity.get("calendarDate"),
    ]
    for value in candidates:
        if not value or not isinstance(value, str):
            continue
        if value[:10] == fetch_date.isoformat():
            return True
    return False


def try_get_activities_for_date(client: Garmin, fetch_date: date) -> List[dict]:
    date_text = fetch_date.isoformat()

    if hasattr(client, "get_activities_for_date"):
        try:
            result = client.get_activities_for_date(date_text)
            activities = normalize_activity_rows(result)
            if activities:
                return activities
        except TypeError:
            pass

    if hasattr(client, "get_activities_by_date"):
        for args in [
            (date_text, date_text),
            (date_text, date_text, ""),
            (date_text, date_text, None),
        ]:
            try:
                result = client.get_activities_by_date(*args)
                activities = normalize_activity_rows(result)
                if activities:
                    return activities
            except TypeError:
                continue

    if hasattr(client, "get_activities"):
        for start in (0, 1):
            try:
                result = client.get_activities(start, 100)
                activities = normalize_activity_rows(result)
                matched = [
                    activity
                    for activity in activities
                    if activity_date_matches(activity, fetch_date)
                ]
                if matched:
                    return matched
            except TypeError:
                continue

    return []


def get_original_download_format(client: Garmin):
    if ActivityDownloadFormat is not None:
        return ActivityDownloadFormat.ORIGINAL
    if hasattr(client, "ActivityDownloadFormat"):
        return client.ActivityDownloadFormat.ORIGINAL
    return "original"


def save_activity_original(activity_id: int, payload: bytes) -> Path:
    RAW_ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)
    if payload[:2] == b"PK":
        target = RAW_ACTIVITY_DIR / f"{activity_id}.zip"
    else:
        target = RAW_ACTIVITY_DIR / f"{activity_id}.fit"
    target.write_bytes(payload)
    return target


def extract_fit_paths(raw_path: Path) -> List[Path]:
    if raw_path.suffix.lower() == ".fit":
        return [raw_path]

    if raw_path.suffix.lower() != ".zip":
        return []

    with TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        with zipfile.ZipFile(raw_path) as archive:
            archive.extractall(tmp_root)
        extracted = sorted(tmp_root.rglob("*.fit"))
        persistent_paths: List[Path] = []
        for fit_path in extracted:
            target = RAW_ACTIVITY_DIR / f"{raw_path.stem}-{fit_path.name}"
            target.write_bytes(fit_path.read_bytes())
            persistent_paths.append(target)
        return persistent_paths


def parse_fit_heart_rate_samples(
    fit_path: Path,
    activity_id: int,
    tz: ZoneInfo,
) -> List[Tuple[int, str, str, int, str]]:
    fit_file = FitFile(str(fit_path))
    rows: List[Tuple[int, str, str, int, str]] = []
    for record in fit_file.get_messages("record"):
        values = {}
        for field in record:
            values[field.name] = field.value

        bpm = safe_int(values.get("heart_rate"))
        timestamp = values.get("timestamp")
        if bpm is None or bpm <= 0 or timestamp is None:
            continue

        if isinstance(timestamp, datetime):
            timestamp_utc = timestamp
        else:
            continue

        if timestamp_utc.tzinfo is None:
            timestamp_utc = timestamp_utc.replace(tzinfo=timezone.utc)
        else:
            timestamp_utc = timestamp_utc.astimezone(timezone.utc)

        timestamp_local = timestamp_utc.astimezone(tz)
        rows.append(
            (
                activity_id,
                timestamp_utc.isoformat(),
                timestamp_local.isoformat(),
                bpm,
                str(fit_path),
            )
        )

    rows.sort(key=lambda row: row[1])
    return rows


def upsert_activity(
    conn: sqlite3.Connection,
    activity: dict,
    raw_path: Path,
    rows: Sequence[Tuple[int, str, str, int, str]],
) -> None:
    activity_id = safe_int(activity.get("activityId"))
    if activity_id is None:
        raise RuntimeError("Missing activityId in Garmin activity payload")

    fetched_at_utc = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "DELETE FROM activity_heart_rate_samples WHERE activity_id = ?",
        (activity_id,),
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO activity_heart_rate_samples (
            activity_id,
            timestamp_utc,
            timestamp_local,
            bpm,
            source_file
        ) VALUES (?, ?, ?, ?, ?)
        """,
        list(rows),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO activities (
            activity_id,
            activity_name,
            activity_type,
            calendar_date,
            start_time_local,
            start_time_gmt,
            duration_seconds,
            distance_meters,
            source_file,
            fetched_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            activity_id,
            activity.get("activityName"),
            (
                (activity.get("activityType") or {}).get("typeKey")
                if isinstance(activity.get("activityType"), dict)
                else activity.get("activityType")
            ),
            (activity.get("startTimeLocal") or "")[:10] or activity.get("calendarDate"),
            activity.get("startTimeLocal"),
            activity.get("startTimeGMT"),
            safe_float(activity.get("duration")) or safe_float(activity.get("durationSeconds")),
            safe_float(activity.get("distance")),
            str(raw_path),
            fetched_at_utc,
        ),
    )
    conn.commit()


def fetch_activity_fit_data(
    client: Garmin,
    conn: sqlite3.Connection,
    fetch_dates: Sequence[date],
    tz: ZoneInfo,
) -> None:
    download_format = get_original_download_format(client)

    for fetch_date in fetch_dates:
        activities = try_get_activities_for_date(client, fetch_date)
        print(f"[activity] {fetch_date.isoformat()} matched={len(activities)}")

        for activity in activities:
            activity_id = safe_int(activity.get("activityId"))
            if activity_id is None:
                continue

            print(f"[activity] download {activity_id}")
            payload = client.download_activity(activity_id, dl_fmt=download_format)
            if not isinstance(payload, (bytes, bytearray)):
                raise RuntimeError(
                    f"Unexpected download payload for activity {activity_id}: {type(payload)}"
                )

            raw_path = save_activity_original(activity_id, bytes(payload))
            fit_paths = extract_fit_paths(raw_path)
            total_rows: List[Tuple[int, str, str, int, str]] = []
            for fit_path in fit_paths:
                total_rows.extend(parse_fit_heart_rate_samples(fit_path, activity_id, tz))

            upsert_activity(conn, activity, raw_path, total_rows)
            print(f"[activity] saved {activity_id} hr_samples={len(total_rows)}")


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    tz = get_timezone()
    args = parse_args()
    fetch_dates = resolve_dates(args, tz)
    client = create_client()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    if not args.skip_wellness:
        fetch_wellness_for_dates(client, conn, fetch_dates, tz)
    if not args.skip_activities:
        fetch_activity_fit_data(client, conn, fetch_dates, tz)

    conn.close()


if __name__ == "__main__":
    main()
