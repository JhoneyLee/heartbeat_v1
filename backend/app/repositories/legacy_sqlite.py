"""Read-only accessors for the current local SQLite analysis database."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _date_text(value: date) -> str:
    return value.isoformat()


def _ensure_db_exists(db_path: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Local Garmin SQLite database not found: {db_path}")


def load_overview(db_path: Path, start: date, end: date) -> dict[str, object]:
    _ensure_db_exists(db_path)
    with _connect(db_path) as conn:
        has_stress = _table_exists(conn, "daily_stress_summary")
        has_sleep = _table_exists(conn, "daily_sleep_summary")
        summary_row = conn.execute(
            """
            SELECT
                COUNT(*) AS day_count,
                AVG(resting_heart_rate) AS avg_resting_heart_rate,
                AVG(average_heart_rate) AS avg_daily_heart_rate,
                AVG(max_heart_rate) AS avg_daily_max_heart_rate,
                SUM(sample_count) AS total_samples
            FROM daily_summary
            WHERE calendar_date BETWEEN ? AND ?
            """,
            (_date_text(start), _date_text(end)),
        ).fetchone()
        stress_row = (
            conn.execute(
                """
                SELECT
                    AVG(average_stress_level) AS avg_stress_level,
                    AVG(max_stress_level) AS avg_max_stress_level
                FROM daily_stress_summary
                WHERE calendar_date BETWEEN ? AND ?
                """,
                (_date_text(start), _date_text(end)),
            ).fetchone()
            if has_stress
            else None
        )
        sleep_row = (
            conn.execute(
                """
                SELECT
                    AVG(total_sleep_seconds) AS avg_sleep_seconds,
                    AVG(sleep_score) AS avg_sleep_score
                FROM daily_sleep_summary
                WHERE sleep_date BETWEEN ? AND ?
                """,
                (_date_text(start), _date_text(end)),
            ).fetchone()
            if has_sleep
            else None
        )
        activity_row = conn.execute(
            """
            SELECT
                COUNT(*) AS activity_count,
                SUM(CASE WHEN activity_type = 'running' THEN 1 ELSE 0 END) AS running_activity_count
            FROM activities
            WHERE calendar_date BETWEEN ? AND ?
            """,
            (_date_text(start), _date_text(end)),
        ).fetchone()

    return {
        "day_count": int(summary_row["day_count"] or 0),
        "avg_resting_heart_rate": round(float(summary_row["avg_resting_heart_rate"]), 2)
        if summary_row["avg_resting_heart_rate"] is not None
        else None,
        "avg_daily_heart_rate": round(float(summary_row["avg_daily_heart_rate"]), 2)
        if summary_row["avg_daily_heart_rate"] is not None
        else None,
        "avg_daily_max_heart_rate": round(float(summary_row["avg_daily_max_heart_rate"]), 2)
        if summary_row["avg_daily_max_heart_rate"] is not None
        else None,
        "avg_stress_level": round(float(stress_row["avg_stress_level"]), 2)
        if stress_row is not None and stress_row["avg_stress_level"] is not None
        else None,
        "avg_max_stress_level": round(float(stress_row["avg_max_stress_level"]), 2)
        if stress_row is not None and stress_row["avg_max_stress_level"] is not None
        else None,
        "avg_sleep_seconds": round(float(sleep_row["avg_sleep_seconds"]), 2)
        if sleep_row is not None and sleep_row["avg_sleep_seconds"] is not None
        else None,
        "avg_sleep_score": round(float(sleep_row["avg_sleep_score"]), 2)
        if sleep_row is not None and sleep_row["avg_sleep_score"] is not None
        else None,
        "total_samples": int(summary_row["total_samples"] or 0),
        "activity_count": int(activity_row["activity_count"] or 0),
        "running_activity_count": int(activity_row["running_activity_count"] or 0),
        "available_metrics": {
            "heart_rate": True,
            "stress": has_stress,
            "sleep": has_sleep,
            "events": False,
        },
    }


def load_daily_heart_rate(db_path: Path, start: date, end: date) -> list[dict[str, object]]:
    _ensure_db_exists(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                calendar_date,
                resting_heart_rate,
                min_heart_rate,
                max_heart_rate,
                average_heart_rate,
                sample_count
            FROM daily_summary
            WHERE calendar_date BETWEEN ? AND ?
            ORDER BY calendar_date
            """,
            (_date_text(start), _date_text(end)),
        ).fetchall()

    return [
        {
            "calendar_date": row["calendar_date"],
            "resting_heart_rate": row["resting_heart_rate"],
            "min_heart_rate": row["min_heart_rate"],
            "max_heart_rate": row["max_heart_rate"],
            "average_heart_rate": round(float(row["average_heart_rate"]), 2)
            if row["average_heart_rate"] is not None
            else None,
            "sample_count": int(row["sample_count"] or 0),
        }
        for row in rows
    ]


def load_hourly_profile(db_path: Path, start: date, end: date) -> list[dict[str, object]]:
    _ensure_db_exists(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                CAST(substr(timestamp_local, 12, 2) AS INTEGER) AS hour,
                AVG(bpm) AS average_bpm,
                COUNT(*) AS sample_count
            FROM heart_rate_samples
            WHERE source = 'wellness'
              AND calendar_date BETWEEN ? AND ?
            GROUP BY hour
            ORDER BY hour
            """,
            (_date_text(start), _date_text(end)),
        ).fetchall()

    return [
        {
            "hour": int(row["hour"]),
            "average_bpm": round(float(row["average_bpm"]), 2),
            "sample_count": int(row["sample_count"]),
        }
        for row in rows
    ]


def load_activities(db_path: Path, start: date, end: date) -> list[dict[str, object]]:
    _ensure_db_exists(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                a.activity_id,
                a.activity_name,
                a.activity_type,
                a.calendar_date,
                a.start_time_local,
                a.duration_seconds,
                a.distance_meters,
                COUNT(s.bpm) AS sample_count,
                AVG(s.bpm) AS average_heart_rate,
                MAX(s.bpm) AS max_heart_rate
            FROM activities a
            LEFT JOIN activity_heart_rate_samples s
              ON s.activity_id = a.activity_id
            WHERE a.calendar_date BETWEEN ? AND ?
            GROUP BY
                a.activity_id,
                a.activity_name,
                a.activity_type,
                a.calendar_date,
                a.start_time_local,
                a.duration_seconds,
                a.distance_meters
            ORDER BY a.start_time_local
            """,
            (_date_text(start), _date_text(end)),
        ).fetchall()

    return [
        {
            "activity_id": int(row["activity_id"]),
            "activity_name": row["activity_name"],
            "activity_type": row["activity_type"],
            "calendar_date": row["calendar_date"],
            "start_time_local": row["start_time_local"],
            "duration_seconds": float(row["duration_seconds"])
            if row["duration_seconds"] is not None
            else None,
            "distance_meters": float(row["distance_meters"])
            if row["distance_meters"] is not None
            else None,
            "sample_count": int(row["sample_count"] or 0),
            "average_heart_rate": round(float(row["average_heart_rate"]), 2)
            if row["average_heart_rate"] is not None
            else None,
            "max_heart_rate": int(row["max_heart_rate"])
            if row["max_heart_rate"] is not None
            else None,
        }
        for row in rows
    ]


def load_activity_samples(db_path: Path, activity_id: int) -> list[dict[str, object]]:
    _ensure_db_exists(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT timestamp_local, bpm
            FROM activity_heart_rate_samples
            WHERE activity_id = ?
            ORDER BY timestamp_local
            """,
            (activity_id,),
        ).fetchall()

    return [
        {
            "timestamp_local": row["timestamp_local"],
            "bpm": int(row["bpm"]),
        }
        for row in rows
    ]


def load_daily_stress(db_path: Path, start: date, end: date) -> list[dict[str, object]]:
    _ensure_db_exists(db_path)
    with _connect(db_path) as conn:
        if not _table_exists(conn, "daily_stress_summary"):
            return []
        rows = conn.execute(
            """
            SELECT
                calendar_date,
                average_stress_level,
                max_stress_level,
                sample_count,
                body_battery_sample_count
            FROM daily_stress_summary
            WHERE calendar_date BETWEEN ? AND ?
            ORDER BY calendar_date
            """,
            (_date_text(start), _date_text(end)),
        ).fetchall()

    return [
        {
            "calendar_date": row["calendar_date"],
            "average_stress_level": round(float(row["average_stress_level"]), 2)
            if row["average_stress_level"] is not None
            else None,
            "max_stress_level": int(row["max_stress_level"])
            if row["max_stress_level"] is not None
            else None,
            "sample_count": int(row["sample_count"] or 0),
            "body_battery_sample_count": int(row["body_battery_sample_count"] or 0),
        }
        for row in rows
    ]


def load_daily_sleep(db_path: Path, start: date, end: date) -> list[dict[str, object]]:
    _ensure_db_exists(db_path)
    with _connect(db_path) as conn:
        if not _table_exists(conn, "daily_sleep_summary"):
            return []
        rows = conn.execute(
            """
            SELECT
                sleep_date,
                sleep_start_local,
                sleep_end_local,
                total_sleep_seconds,
                deep_sleep_seconds,
                light_sleep_seconds,
                rem_sleep_seconds,
                awake_sleep_seconds,
                average_sleep_stress,
                average_sleep_heart_rate,
                resting_heart_rate,
                sleep_score
            FROM daily_sleep_summary
            WHERE sleep_date BETWEEN ? AND ?
            ORDER BY sleep_date
            """,
            (_date_text(start), _date_text(end)),
        ).fetchall()

    return [
        {
            "sleep_date": row["sleep_date"],
            "sleep_start_local": row["sleep_start_local"],
            "sleep_end_local": row["sleep_end_local"],
            "total_sleep_seconds": int(row["total_sleep_seconds"])
            if row["total_sleep_seconds"] is not None
            else None,
            "deep_sleep_seconds": int(row["deep_sleep_seconds"])
            if row["deep_sleep_seconds"] is not None
            else None,
            "light_sleep_seconds": int(row["light_sleep_seconds"])
            if row["light_sleep_seconds"] is not None
            else None,
            "rem_sleep_seconds": int(row["rem_sleep_seconds"])
            if row["rem_sleep_seconds"] is not None
            else None,
            "awake_sleep_seconds": int(row["awake_sleep_seconds"])
            if row["awake_sleep_seconds"] is not None
            else None,
            "average_sleep_stress": round(float(row["average_sleep_stress"]), 2)
            if row["average_sleep_stress"] is not None
            else None,
            "average_sleep_heart_rate": round(float(row["average_sleep_heart_rate"]), 2)
            if row["average_sleep_heart_rate"] is not None
            else None,
            "resting_heart_rate": int(row["resting_heart_rate"])
            if row["resting_heart_rate"] is not None
            else None,
            "sleep_score": int(row["sleep_score"]) if row["sleep_score"] is not None else None,
        }
        for row in rows
    ]
