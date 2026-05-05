#!/usr/bin/env python3
"""Fetch Garmin Connect heart rate data and persist it locally."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from getpass import getpass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from garminconnect import Garmin


ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw" / "heart_rate"
DB_PATH = ROOT_DIR / "data" / "processed" / "garmin_heart_rate.sqlite3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Garmin Connect heart rate data for one or more dates."
    )
    parser.add_argument(
        "--date",
        help="Single date to fetch in YYYY-MM-DD format. Defaults to today in Garmin timezone.",
    )
    parser.add_argument(
        "--start-date",
        help="Start date to fetch in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-date",
        help="End date to fetch in YYYY-MM-DD format. Defaults to start date.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of recent days to fetch when no explicit date range is provided.",
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
            PRIMARY KEY (timestamp_utc, bpm)
        )
        """
    )
    conn.commit()


def safe_int(value: object) -> Optional[int]:
    if value in (None, "", -1):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def heart_rate_average(samples: Sequence[Tuple[str, int]]) -> Optional[float]:
    if not samples:
        return None
    return round(sum(bpm for _, bpm in samples) / len(samples), 2)


def normalize_samples(
    heart_rate_values: Iterable[Sequence[object]],
    tz: ZoneInfo,
) -> List[Tuple[str, int]]:
    normalized: List[Tuple[str, int]] = []
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


def raw_file_path(fetch_date: date) -> Path:
    return RAW_DIR / f"{fetch_date.isoformat()}.json"


def save_raw_json(payload: dict, fetch_date: date) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = raw_file_path(fetch_date)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def upsert_day(
    conn: sqlite3.Connection,
    fetch_date: date,
    raw_path: Path,
    payload: dict,
    samples: Sequence[Tuple[str, int]],
) -> None:
    fetched_at_utc = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "DELETE FROM heart_rate_samples WHERE calendar_date = ?",
        (fetch_date.isoformat(),),
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO heart_rate_samples (
            calendar_date,
            timestamp_utc,
            timestamp_local,
            bpm,
            raw_file
        ) VALUES (?, ?, ?, ?, ?)
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


def fetch_and_store(
    client: Garmin,
    fetch_dates: Sequence[date],
    tz: ZoneInfo,
) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    for fetch_date in fetch_dates:
        date_text = fetch_date.isoformat()
        print(f"[fetch] {date_text}")
        payload = client.get_heart_rates(date_text)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected Garmin payload for {date_text}: {type(payload)}")

        samples = normalize_samples(payload.get("heartRateValues", []), tz)
        raw_path = save_raw_json(payload, fetch_date)
        upsert_day(conn, fetch_date, raw_path, payload, samples)
        print(
            f"[saved] {date_text} samples={len(samples)} "
            f"resting={safe_int(payload.get('restingHeartRate'))} "
            f"max={safe_int(payload.get('maxHeartRate'))}"
        )

    conn.close()


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    tz = get_timezone()
    args = parse_args()
    fetch_dates = resolve_dates(args, tz)
    client = create_client()
    fetch_and_store(client, fetch_dates, tz=tz)


if __name__ == "__main__":
    main()
