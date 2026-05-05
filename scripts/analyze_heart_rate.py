#!/usr/bin/env python3
"""Analyze locally stored Garmin Connect heart rate data."""

from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "processed" / "garmin_heart_rate.sqlite3"
REPORT_DIR = ROOT_DIR / "reports"
SUMMARY_CSV = REPORT_DIR / "heart_rate_daily_summary.csv"
SUMMARY_TXT = REPORT_DIR / "heart_rate_summary.txt"
TREND_PNG = REPORT_DIR / "heart_rate_trend.png"
HOURLY_PNG = REPORT_DIR / "heart_rate_hourly_profile.png"


@dataclass
class DailySummary:
    calendar_date: str
    resting_heart_rate: Optional[int]
    min_heart_rate: Optional[int]
    max_heart_rate: Optional[int]
    average_heart_rate: Optional[float]
    sample_count: int


def load_daily_summaries(conn: sqlite3.Connection) -> List[DailySummary]:
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
        ORDER BY calendar_date
        """
    ).fetchall()
    return [DailySummary(*row) for row in rows]


def load_hourly_profile(conn: sqlite3.Connection) -> Dict[int, float]:
    rows = conn.execute(
        """
        SELECT timestamp_local, bpm
        FROM heart_rate_samples
        ORDER BY timestamp_local
        """
    ).fetchall()
    hourly_values: Dict[int, List[int]] = defaultdict(list)
    for timestamp_local, bpm in rows:
        hour = datetime.fromisoformat(timestamp_local).hour
        hourly_values[hour].append(int(bpm))

    return {
        hour: round(sum(values) / len(values), 2)
        for hour, values in sorted(hourly_values.items())
        if values
    }


def write_summary_csv(summaries: List[DailySummary]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "calendar_date",
                "resting_heart_rate",
                "min_heart_rate",
                "max_heart_rate",
                "average_heart_rate",
                "sample_count",
            ]
        )
        for item in summaries:
            writer.writerow(
                [
                    item.calendar_date,
                    item.resting_heart_rate,
                    item.min_heart_rate,
                    item.max_heart_rate,
                    item.average_heart_rate,
                    item.sample_count,
                ]
            )


def write_text_summary(summaries: List[DailySummary], hourly_profile: Dict[int, float]) -> None:
    if not summaries:
        SUMMARY_TXT.write_text("No heart rate data found.\n", encoding="utf-8")
        return

    resting_values = [item.resting_heart_rate for item in summaries if item.resting_heart_rate]
    avg_values = [item.average_heart_rate for item in summaries if item.average_heart_rate]
    peak_values = [item.max_heart_rate for item in summaries if item.max_heart_rate]

    lines = [
        f"days_analyzed: {len(summaries)}",
        f"date_range: {summaries[0].calendar_date} .. {summaries[-1].calendar_date}",
        f"avg_resting_hr: {round(sum(resting_values) / len(resting_values), 2) if resting_values else 'n/a'}",
        f"avg_daily_hr: {round(sum(avg_values) / len(avg_values), 2) if avg_values else 'n/a'}",
        f"avg_daily_max_hr: {round(sum(peak_values) / len(peak_values), 2) if peak_values else 'n/a'}",
    ]

    if hourly_profile:
        peak_hour = max(hourly_profile, key=hourly_profile.get)
        low_hour = min(hourly_profile, key=hourly_profile.get)
        lines.extend(
            [
                f"highest_hourly_avg: {peak_hour:02d}:00 ({hourly_profile[peak_hour]} bpm)",
                f"lowest_hourly_avg: {low_hour:02d}:00 ({hourly_profile[low_hour]} bpm)",
            ]
        )

    SUMMARY_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def maybe_render_charts(summaries: List[DailySummary], hourly_profile: Dict[int, float]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is not installed, skipping PNG chart generation.")
        return

    if not summaries:
        return

    dates = [item.calendar_date for item in summaries]
    resting = [item.resting_heart_rate for item in summaries]
    average = [item.average_heart_rate for item in summaries]
    maximum = [item.max_heart_rate for item in summaries]

    plt.figure(figsize=(12, 6))
    plt.plot(dates, resting, label="Resting HR", marker="o")
    plt.plot(dates, average, label="Average HR", marker="o")
    plt.plot(dates, maximum, label="Max HR", marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("BPM")
    plt.title("Garmin Heart Rate Trend")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(TREND_PNG, dpi=160)
    plt.close()

    if hourly_profile:
        hours = list(hourly_profile.keys())
        bpm_values = list(hourly_profile.values())
        plt.figure(figsize=(12, 5))
        plt.plot(hours, bpm_values, marker="o")
        plt.xticks(hours, [f"{hour:02d}" for hour in hours])
        plt.xlabel("Hour of Day")
        plt.ylabel("Average BPM")
        plt.title("Average Heart Rate by Hour")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(HOURLY_PNG, dpi=160)
        plt.close()


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(
            f"Database not found: {DB_PATH}\nRun scripts/fetch_garmin_heart_rate.py first."
        )

    conn = sqlite3.connect(DB_PATH)
    summaries = load_daily_summaries(conn)
    hourly_profile = load_hourly_profile(conn)
    conn.close()

    write_summary_csv(summaries)
    write_text_summary(summaries, hourly_profile)
    maybe_render_charts(summaries, hourly_profile)

    print(f"Saved {SUMMARY_CSV}")
    print(f"Saved {SUMMARY_TXT}")
    if TREND_PNG.exists():
        print(f"Saved {TREND_PNG}")
    if HOURLY_PNG.exists():
        print(f"Saved {HOURLY_PNG}")


if __name__ == "__main__":
    main()
