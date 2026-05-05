#!/usr/bin/env python3
"""Analyze locally stored Garmin Connect heart rate data."""

from __future__ import annotations

import csv
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "processed" / "garmin_heart_rate.sqlite3"
REPORT_DIR = ROOT_DIR / "reports"
MPL_CONFIG_DIR = ROOT_DIR / ".mplconfig"
REPORT_DATA_DIR = REPORT_DIR / "dashboard_data"
ACTIVITY_DATA_DIR = REPORT_DATA_DIR / "activities"
SUMMARY_CSV = REPORT_DIR / "heart_rate_daily_summary.csv"
SUMMARY_TXT = REPORT_DIR / "heart_rate_summary.txt"
TREND_PNG = REPORT_DIR / "heart_rate_trend.png"
HOURLY_PNG = REPORT_DIR / "heart_rate_hourly_profile.png"
DASHBOARD_HTML = REPORT_DIR / "heart_rate_dashboard.html"
DASHBOARD_DATA_JS = REPORT_DATA_DIR / "dashboard_data.js"


@dataclass
class DailySummary:
    calendar_date: str
    resting_heart_rate: Optional[int]
    min_heart_rate: Optional[int]
    max_heart_rate: Optional[int]
    average_heart_rate: Optional[float]
    sample_count: int


@dataclass
class ActivitySummary:
    activity_id: int
    activity_name: Optional[str]
    activity_type: Optional[str]
    calendar_date: Optional[str]
    start_time_local: Optional[str]
    duration_seconds: Optional[float]
    distance_meters: Optional[float]
    sample_count: int
    average_heart_rate: Optional[float]
    max_heart_rate: Optional[int]


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
        WHERE source = 'wellness'
        ORDER BY timestamp_local
        """
    ).fetchall()
    hourly_values: Dict[int, List[int]] = {}
    for timestamp_local, bpm in rows:
        hour = datetime.fromisoformat(timestamp_local).hour
        hourly_values.setdefault(hour, []).append(int(bpm))

    return {
        hour: round(sum(values) / len(values), 2)
        for hour, values in sorted(hourly_values.items())
        if values
    }


def load_daily_hourly_bins(conn: sqlite3.Connection) -> List[dict]:
    rows = conn.execute(
        """
        SELECT
            calendar_date,
            CAST(substr(timestamp_local, 12, 2) AS INTEGER) AS hour,
            AVG(bpm) AS average_bpm,
            COUNT(*) AS sample_count
        FROM heart_rate_samples
        WHERE source = 'wellness'
        GROUP BY calendar_date, hour
        ORDER BY calendar_date, hour
        """
    ).fetchall()
    return [
        {
            "calendar_date": calendar_date,
            "hour": int(hour),
            "average_bpm": round(float(average_bpm), 2),
            "sample_count": int(sample_count),
        }
        for calendar_date, hour, average_bpm, sample_count in rows
    ]


def load_activity_summaries(conn: sqlite3.Connection) -> List[ActivitySummary]:
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
        GROUP BY
            a.activity_id,
            a.activity_name,
            a.activity_type,
            a.calendar_date,
            a.start_time_local,
            a.duration_seconds,
            a.distance_meters
        ORDER BY a.start_time_local
        """
    ).fetchall()
    activities: List[ActivitySummary] = []
    for row in rows:
        activity_id = int(row[0])
        activity_name = row[1]
        activity_type = row[2]
        calendar_date = row[3]
        start_time_local = row[4]
        duration_seconds = float(row[5]) if row[5] is not None else None
        distance_meters = float(row[6]) if row[6] is not None else None
        sample_count = int(row[7])
        average_heart_rate = round(float(row[8]), 2) if row[8] is not None else None
        max_heart_rate = int(row[9]) if row[9] is not None else None
        activities.append(
            ActivitySummary(
                activity_id=activity_id,
                activity_name=activity_name,
                activity_type=activity_type,
                calendar_date=calendar_date,
                start_time_local=start_time_local,
                duration_seconds=duration_seconds,
                distance_meters=distance_meters,
                sample_count=sample_count,
                average_heart_rate=average_heart_rate,
                max_heart_rate=max_heart_rate,
            )
        )
    return activities


def load_activity_samples(conn: sqlite3.Connection, activity_id: int) -> List[dict]:
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
        {"timestamp_local": timestamp_local, "bpm": int(bpm)}
        for timestamp_local, bpm in rows
    ]


def load_running_daily_trend(conn: sqlite3.Connection) -> List[dict]:
    rows = conn.execute(
        """
        SELECT
            a.calendar_date,
            COUNT(DISTINCT a.activity_id) AS activity_count,
            COUNT(s.bpm) AS sample_count,
            AVG(s.bpm) AS average_heart_rate,
            MAX(s.bpm) AS max_heart_rate
        FROM activities a
        JOIN activity_heart_rate_samples s
            ON s.activity_id = a.activity_id
        WHERE a.activity_type = 'running'
        GROUP BY a.calendar_date
        ORDER BY a.calendar_date
        """
    ).fetchall()
    return [
        {
            "calendar_date": calendar_date,
            "activity_count": int(activity_count),
            "sample_count": int(sample_count),
            "average_heart_rate": round(float(average_heart_rate), 2)
            if average_heart_rate is not None
            else None,
            "max_heart_rate": int(max_heart_rate) if max_heart_rate is not None else None,
        }
        for calendar_date, activity_count, sample_count, average_heart_rate, max_heart_rate in rows
    ]


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


def write_dashboard_data(
    summaries: List[DailySummary],
    daily_hourly_bins: List[dict],
    activities: List[ActivitySummary],
    running_daily_trend: List[dict],
    asset_version: str,
    conn: sqlite3.Connection,
) -> None:
    REPORT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVITY_DATA_DIR.mkdir(parents=True, exist_ok=True)

    summary_payload = {
        "generated_at": datetime.now().isoformat(),
        "asset_version": asset_version,
        "daily_summaries": [
            {
                "calendar_date": item.calendar_date,
                "resting_heart_rate": item.resting_heart_rate,
                "min_heart_rate": item.min_heart_rate,
                "max_heart_rate": item.max_heart_rate,
                "average_heart_rate": item.average_heart_rate,
                "sample_count": item.sample_count,
            }
            for item in summaries
        ],
        "daily_hourly_bins": daily_hourly_bins,
        "running_daily_trend": running_daily_trend,
        "activities": [
            {
                "activity_id": item.activity_id,
                "activity_name": item.activity_name,
                "activity_type": item.activity_type,
                "calendar_date": item.calendar_date,
                "start_time_local": item.start_time_local,
                "duration_seconds": item.duration_seconds,
                "distance_meters": item.distance_meters,
                "sample_count": item.sample_count,
                "average_heart_rate": item.average_heart_rate,
                "max_heart_rate": item.max_heart_rate,
                "data_path": f"./dashboard_data/activities/{item.activity_id}.js?v={asset_version}",
            }
            for item in activities
        ],
    }
    DASHBOARD_DATA_JS.write_text(
        "window.__GARMIN_DASHBOARD__ = "
        + json.dumps(summary_payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )

    for item in activities:
        samples = load_activity_samples(conn, item.activity_id)
        sample_payload = {
            "activity_id": item.activity_id,
            "activity_name": item.activity_name,
            "activity_type": item.activity_type,
            "calendar_date": item.calendar_date,
            "start_time_local": item.start_time_local,
            "duration_seconds": item.duration_seconds,
            "distance_meters": item.distance_meters,
            "sample_count": item.sample_count,
            "average_heart_rate": item.average_heart_rate,
            "max_heart_rate": item.max_heart_rate,
            "samples": samples,
        }
        (ACTIVITY_DATA_DIR / f"{item.activity_id}.js").write_text(
            "window.__GARMIN_ACTIVITY_DATA__ = window.__GARMIN_ACTIVITY_DATA__ || {};\n"
            f"window.__GARMIN_ACTIVITY_DATA__[{item.activity_id}] = "
            + json.dumps(sample_payload, ensure_ascii=False)
            + ";\n",
            encoding="utf-8",
        )


def write_html_dashboard(asset_version: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    html = """<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Garmin Heart Rate Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="./dashboard_data/dashboard_data.js?v={asset_version}"></script>
    <style>
      :root {
        --bg: #f3efe6;
        --panel: #fffaf2;
        --ink: #1f1d1a;
        --muted: #6c665e;
        --line: #ded3c2;
        --accent: #c65d3a;
        --accent-2: #2f6c73;
        --accent-3: #c7a43a;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Avenir Next", "Helvetica Neue", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(198, 93, 58, 0.14), transparent 24%),
          radial-gradient(circle at top right, rgba(47, 108, 115, 0.14), transparent 24%),
          var(--bg);
        color: var(--ink);
      }
      .wrap {
        max-width: 1240px;
        margin: 0 auto;
        padding: 28px 18px 48px;
      }
      h1 {
        margin: 0 0 6px;
        font-size: clamp(34px, 6vw, 58px);
        line-height: 0.94;
        letter-spacing: -0.05em;
      }
      .sub {
        color: var(--muted);
        margin-bottom: 18px;
      }
      .toolbar {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        align-items: end;
        margin-bottom: 18px;
      }
      .toolbar-spacer {
        flex: 1 1 auto;
      }
      .control {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .control label {
        font-size: 12px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
      input, select, button {
        border: 1px solid var(--line);
        background: var(--panel);
        color: var(--ink);
        border-radius: 14px;
        padding: 10px 12px;
        font: inherit;
      }
      button {
        cursor: pointer;
      }
      .presets {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin-bottom: 18px;
      }
      .card, .chart-card {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 18px;
        box-shadow: 0 14px 35px rgba(36, 29, 18, 0.05);
      }
      .label {
        color: var(--muted);
        font-size: 12px;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }
      .value {
        font-size: 30px;
        font-weight: 700;
        letter-spacing: -0.03em;
      }
      .charts {
        display: flex;
        flex-direction: column;
        gap: 18px;
        margin-bottom: 18px;
      }
      .wide-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 18px;
        margin-bottom: 18px;
      }
      .chart-card canvas {
        display: block;
        width: 100% !important;
        height: 100% !important;
      }
      .chart-title {
        margin: 0 0 12px;
        font-size: 20px;
      }
      .chart-frame {
        position: relative;
        width: 100%;
        height: 360px;
        min-height: 360px;
        max-height: 360px;
      }
      .activity-frame {
        position: relative;
        width: 100%;
        height: 320px;
        min-height: 320px;
        max-height: 320px;
      }
      .activity-layout {
        display: grid;
        grid-template-columns: 320px 1fr;
        gap: 18px;
      }
      .activity-meta {
        color: var(--muted);
        line-height: 1.6;
      }
      .empty {
        color: var(--muted);
        font-size: 15px;
      }
      .summary {
        white-space: pre-wrap;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        color: var(--muted);
        line-height: 1.6;
      }
      .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 10px;
      }
      .pill {
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 6px 10px;
        color: var(--muted);
        font-size: 13px;
      }
      .anomaly-list {
        margin: 0;
        padding-left: 18px;
        color: var(--muted);
        line-height: 1.65;
      }
      .anomaly-list li + li {
        margin-top: 8px;
      }
      .muted {
        color: var(--muted);
      }
      @media (max-width: 960px) {
        .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .wide-grid { grid-template-columns: 1fr; }
        .activity-layout { grid-template-columns: 1fr; }
      }
      @media (max-width: 560px) {
        .grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Heart Rate Dashboard</h1>
      <div class="sub">기본 보기: 최근 28일. 기간을 바꾸면 일별 추세와 활동 목록이 함께 갱신됩니다.</div>

      <section class="toolbar">
        <div class="control">
          <label for="startDate">Start</label>
          <input id="startDate" type="date">
        </div>
        <div class="control">
          <label for="endDate">End</label>
          <input id="endDate" type="date">
        </div>
        <div class="control">
          <label for="aggregationSelect">Trend Mode</label>
          <select id="aggregationSelect">
            <option value="day">Daily</option>
            <option value="week">Weekly</option>
            <option value="month">Monthly</option>
          </select>
        </div>
        <div class="control">
          <label for="activityTypeSelect">Activity Type</label>
          <select id="activityTypeSelect"></select>
        </div>
        <div class="toolbar-spacer"></div>
        <div class="control">
          <label>Presets</label>
          <div class="presets">
            <button type="button" data-preset="28">Last 28 Days</button>
            <button type="button" data-preset="90">Last 90 Days</button>
            <button type="button" data-preset="ytd">YTD</button>
            <button type="button" data-preset="all">All</button>
          </div>
        </div>
      </section>

      <section class="grid">
        <div class="card">
          <div class="label">Days</div>
          <div id="daysValue" class="value">-</div>
        </div>
        <div class="card">
          <div class="label">Avg Resting HR</div>
          <div id="restingValue" class="value">-</div>
        </div>
        <div class="card">
          <div class="label">Avg Daily HR</div>
          <div id="avgValue" class="value">-</div>
        </div>
        <div class="card">
          <div class="label">Avg Daily Max HR</div>
          <div id="maxValue" class="value">-</div>
        </div>
      </section>

      <section class="charts">
        <div class="chart-card">
          <h2 class="chart-title">Daily Trend</h2>
          <div class="chart-frame">
            <canvas id="trendChart"></canvas>
          </div>
        </div>
        <div class="chart-card">
          <h2 class="chart-title">Hourly Profile</h2>
          <div class="chart-frame">
            <canvas id="hourlyChart"></canvas>
          </div>
        </div>
        <div class="chart-card">
          <h2 class="chart-title">Running High-Resolution Trend</h2>
          <div class="muted" style="margin-bottom: 12px;">
            running 활동의 고해상도 심박수 샘플을 날짜별로 합쳐 평균과 최대 심박수 대표값을 계산한 추세입니다.
          </div>
          <div class="chart-frame">
            <canvas id="runningTrendChart"></canvas>
          </div>
        </div>
      </section>

      <section class="chart-card" style="margin-bottom: 18px;">
        <h2 class="chart-title">Selected Range Summary</h2>
        <div id="rangeSummary" class="summary">-</div>
        <div id="rangePills" class="pill-row"></div>
      </section>

      <section class="wide-grid">
        <div class="chart-card">
          <h2 class="chart-title">Range Anomalies</h2>
          <ul id="rangeAnomalies" class="anomaly-list"></ul>
        </div>
        <div class="chart-card">
          <h2 class="chart-title">Selected Activity Anomalies</h2>
          <ul id="activityAnomalies" class="anomaly-list"></ul>
        </div>
      </section>

      <section class="chart-card">
        <h2 class="chart-title">Activity Detail</h2>
        <div class="activity-layout">
          <div>
            <div class="control" style="margin-bottom: 14px;">
              <label for="activitySelect">Activity</label>
              <select id="activitySelect"></select>
            </div>
            <div id="activityMeta" class="activity-meta"></div>
          </div>
          <div>
            <div class="activity-frame">
              <canvas id="activityChart"></canvas>
            </div>
            <div id="activityEmpty" class="empty" style="display: none; margin-top: 12px;">
              선택한 기간에 고해상도 활동 심박수 데이터가 없습니다.
            </div>
          </div>
        </div>
      </section>
    </div>

    <script>
      const dashboard = window.__GARMIN_DASHBOARD__ || {
        daily_summaries: [],
        daily_hourly_bins: [],
        running_daily_trend: [],
        activities: []
      };
      window.__GARMIN_ACTIVITY_DATA__ = window.__GARMIN_ACTIVITY_DATA__ || {};
      const allSummaries = dashboard.daily_summaries;
      const allHourlyBins = dashboard.daily_hourly_bins;
      const allRunningTrend = dashboard.running_daily_trend || [];
      const allActivities = dashboard.activities;
      const activityCache = window.__GARMIN_ACTIVITY_DATA__;

      const startInput = document.getElementById("startDate");
      const endInput = document.getElementById("endDate");
      const aggregationSelect = document.getElementById("aggregationSelect");
      const activityTypeSelect = document.getElementById("activityTypeSelect");
      const activitySelect = document.getElementById("activitySelect");
      const activityMeta = document.getElementById("activityMeta");
      const activityEmpty = document.getElementById("activityEmpty");
      const rangeSummary = document.getElementById("rangeSummary");
      const rangePills = document.getElementById("rangePills");
      const rangeAnomalies = document.getElementById("rangeAnomalies");
      const activityAnomalies = document.getElementById("activityAnomalies");
      const daysValue = document.getElementById("daysValue");
      const restingValue = document.getElementById("restingValue");
      const avgValue = document.getElementById("avgValue");
      const maxValue = document.getElementById("maxValue");

      function parseDateOnly(value) {
        return new Date(`${value}T00:00:00`);
      }

      function formatNumber(value) {
        return value == null || Number.isNaN(value) ? "n/a" : Number(value).toFixed(2);
      }

      function formatDuration(seconds) {
        if (!seconds) return "n/a";
        const total = Math.round(seconds);
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const secs = total % 60;
        return [hours, minutes, secs]
          .map((value) => String(value).padStart(2, "0"))
          .join(":");
      }

      function formatDistance(meters) {
        if (!meters) return "n/a";
        return `${(meters / 1000).toFixed(2)} km`;
      }

      function average(values) {
        if (!values.length) return null;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
      }

      function standardDeviation(values) {
        if (values.length < 2) return 0;
        const mean = average(values);
        const variance = average(values.map((value) => (value - mean) ** 2));
        return Math.sqrt(variance);
      }

      function getIsoWeekLabel(dateValue) {
        const date = new Date(`${dateValue}T00:00:00`);
        const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
        const dayNum = target.getUTCDay() || 7;
        target.setUTCDate(target.getUTCDate() + 4 - dayNum);
        const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
        const weekNum = Math.ceil((((target - yearStart) / 86400000) + 1) / 7);
        return `${target.getUTCFullYear()}-W${String(weekNum).padStart(2, "0")}`;
      }

      function getMonthLabel(dateValue) {
        return dateValue.slice(0, 7);
      }

      const trendChart = new Chart(document.getElementById("trendChart"), {
        type: "line",
        data: {
          labels: [],
          datasets: [
            {
              label: "Resting HR",
              data: [],
              borderColor: "#c65d3a",
              backgroundColor: "rgba(198, 93, 58, 0.18)",
              tension: 0.32
            },
            {
              label: "Average HR",
              data: [],
              borderColor: "#2f6c73",
              backgroundColor: "rgba(47, 108, 115, 0.18)",
              tension: 0.32
            },
            {
              label: "Max HR",
              data: [],
              borderColor: "#c7a43a",
              backgroundColor: "rgba(199, 164, 58, 0.18)",
              tension: 0.32
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: "#1f1d1a" }
            }
          },
          scales: {
            x: {
              ticks: { color: "#6c665e" },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            },
            y: {
              ticks: { color: "#6c665e" },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            }
          }
        }
      });

      const hourlyChart = new Chart(document.getElementById("hourlyChart"), {
        type: "bar",
        data: {
          labels: [],
          datasets: [{
            label: "Average BPM",
            data: [],
            backgroundColor: "rgba(47, 108, 115, 0.78)",
            borderRadius: 8
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: "#1f1d1a" } }
          },
          scales: {
            x: {
              ticks: { color: "#6c665e" },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            },
            y: {
              ticks: { color: "#6c665e" },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            }
          }
        }
      });

      const runningTrendChart = new Chart(document.getElementById("runningTrendChart"), {
        type: "line",
        data: {
          labels: [],
          datasets: [
            {
              label: "Running Avg HR",
              data: [],
              borderColor: "#2f6c73",
              backgroundColor: "rgba(47, 108, 115, 0.18)",
              tension: 0.28
            },
            {
              label: "Running Max HR",
              data: [],
              borderColor: "#c7a43a",
              backgroundColor: "rgba(199, 164, 58, 0.18)",
              tension: 0.28
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: { color: "#1f1d1a" }
            }
          },
          scales: {
            x: {
              ticks: { color: "#6c665e" },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            },
            y: {
              ticks: { color: "#6c665e" },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            }
          }
        }
      });

      const activityChart = new Chart(document.getElementById("activityChart"), {
        type: "line",
        data: {
          labels: [],
          datasets: [{
            label: "Activity HR",
            data: [],
            borderColor: "#c65d3a",
            backgroundColor: "rgba(198, 93, 58, 0.18)",
            pointRadius: 0,
            borderWidth: 1.8,
            tension: 0.18
          }, {
            label: "Anomaly",
            data: [],
            type: "scatter",
            pointRadius: 4,
            pointHoverRadius: 5,
            pointBackgroundColor: "#2f6c73",
            pointBorderColor: "#fffaf2",
            pointBorderWidth: 1.5,
            showLine: false
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: "#1f1d1a" } }
          },
          scales: {
            x: {
              ticks: {
                color: "#6c665e",
                maxTicksLimit: 8
              },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            },
            y: {
              ticks: { color: "#6c665e" },
              grid: { color: "rgba(108, 102, 94, 0.12)" }
            }
          }
        }
      });

      function updatePreset(days) {
        if (!allSummaries.length) return;
        const latest = parseDateOnly(allSummaries[allSummaries.length - 1].calendar_date);
        let start;
        if (days === "all") {
          start = parseDateOnly(allSummaries[0].calendar_date);
        } else if (days === "ytd") {
          start = new Date(latest.getFullYear(), 0, 1);
        } else {
          start = new Date(latest);
          start.setDate(start.getDate() - (Number(days) - 1));
        }
        startInput.value = start.toISOString().slice(0, 10);
        endInput.value = latest.toISOString().slice(0, 10);
        renderRange();
      }

      function getSelectedRange() {
        const startValue = startInput.value || (allSummaries[0] && allSummaries[0].calendar_date);
        const endValue = endInput.value || (allSummaries[allSummaries.length - 1] && allSummaries[allSummaries.length - 1].calendar_date);
        return { startValue, endValue };
      }

      function filterSummaries(startValue, endValue) {
        return allSummaries.filter((item) => item.calendar_date >= startValue && item.calendar_date <= endValue);
      }

      function buildHourlyProfile(startValue, endValue) {
        const filtered = allHourlyBins.filter(
          (item) => item.calendar_date >= startValue && item.calendar_date <= endValue
        );
        const grouped = new Map();
        filtered.forEach((item) => {
          const current = grouped.get(item.hour) || { weightedSum: 0, count: 0 };
          current.weightedSum += item.average_bpm * item.sample_count;
          current.count += item.sample_count;
          grouped.set(item.hour, current);
        });
        return Array.from(grouped.entries())
          .sort((a, b) => a[0] - b[0])
          .map(([hour, value]) => ({
            label: `${String(hour).padStart(2, "0")}:00`,
            average: value.count ? Number((value.weightedSum / value.count).toFixed(2)) : null
          }));
      }

      function buildTrendData(filtered, mode) {
        if (mode === "day") {
          return filtered.map((item) => ({
            label: item.calendar_date,
            resting: item.resting_heart_rate,
            average: item.average_heart_rate,
            maximum: item.max_heart_rate,
            sample_count: item.sample_count
          }));
        }

        const grouped = new Map();
        filtered.forEach((item) => {
          const key = mode === "week"
            ? getIsoWeekLabel(item.calendar_date)
            : getMonthLabel(item.calendar_date);
          if (!grouped.has(key)) {
            grouped.set(key, {
              label: key,
              restingValues: [],
              averageValues: [],
              maxValues: [],
              sample_count: 0
            });
          }
          const current = grouped.get(key);
          if (item.resting_heart_rate != null) current.restingValues.push(item.resting_heart_rate);
          if (item.average_heart_rate != null) current.averageValues.push(item.average_heart_rate);
          if (item.max_heart_rate != null) current.maxValues.push(item.max_heart_rate);
          current.sample_count += item.sample_count || 0;
        });

        return Array.from(grouped.values()).map((item) => ({
          label: item.label,
          resting: item.restingValues.length ? Number(average(item.restingValues).toFixed(2)) : null,
          average: item.averageValues.length ? Number(average(item.averageValues).toFixed(2)) : null,
          maximum: item.maxValues.length ? Math.max(...item.maxValues) : null,
          sample_count: item.sample_count
        }));
      }

      function buildRunningTrendData(startValue, endValue, mode) {
        const filtered = allRunningTrend.filter(
          (item) => item.calendar_date >= startValue && item.calendar_date <= endValue
        );

        if (mode === "day") {
          return filtered.map((item) => ({
            label: item.calendar_date,
            average: item.average_heart_rate,
            maximum: item.max_heart_rate,
            sample_count: item.sample_count,
            activity_count: item.activity_count
          }));
        }

        const grouped = new Map();
        filtered.forEach((item) => {
          const key = mode === "week"
            ? getIsoWeekLabel(item.calendar_date)
            : getMonthLabel(item.calendar_date);
          if (!grouped.has(key)) {
            grouped.set(key, {
              label: key,
              weightedAverageSum: 0,
              sample_count: 0,
              maxValues: [],
              activity_count: 0
            });
          }
          const current = grouped.get(key);
          if (item.average_heart_rate != null) {
            current.weightedAverageSum += item.average_heart_rate * item.sample_count;
          }
          current.sample_count += item.sample_count || 0;
          if (item.max_heart_rate != null) {
            current.maxValues.push(item.max_heart_rate);
          }
          current.activity_count += item.activity_count || 0;
        });

        return Array.from(grouped.values()).map((item) => ({
          label: item.label,
          average: item.sample_count
            ? Number((item.weightedAverageSum / item.sample_count).toFixed(2))
            : null,
          maximum: item.maxValues.length ? Math.max(...item.maxValues) : null,
          sample_count: item.sample_count,
          activity_count: item.activity_count
        }));
      }

      function updateSummaryCards(filtered) {
        daysValue.textContent = String(filtered.length);
        const resting = filtered.map((item) => item.resting_heart_rate).filter((value) => value != null);
        const avg = filtered.map((item) => item.average_heart_rate).filter((value) => value != null);
        const maxes = filtered.map((item) => item.max_heart_rate).filter((value) => value != null);
        const restingAvg = resting.length ? resting.reduce((sum, value) => sum + value, 0) / resting.length : null;
        const avgHr = avg.length ? avg.reduce((sum, value) => sum + value, 0) / avg.length : null;
        const maxHr = maxes.length ? maxes.reduce((sum, value) => sum + value, 0) / maxes.length : null;
        restingValue.textContent = formatNumber(restingAvg);
        avgValue.textContent = formatNumber(avgHr);
        maxValue.textContent = formatNumber(maxHr);
      }

      function buildDailyAnomalies(filtered) {
        const anomalies = [];
        const validResting = filtered
          .filter((item) => item.resting_heart_rate != null)
          .map((item) => item.resting_heart_rate);
        const validAverage = filtered
          .filter((item) => item.average_heart_rate != null)
          .map((item) => item.average_heart_rate);
        const validMax = filtered
          .filter((item) => item.max_heart_rate != null)
          .map((item) => item.max_heart_rate);

        const restingMean = average(validResting) || 0;
        const restingStd = standardDeviation(validResting);
        const avgMean = average(validAverage) || 0;
        const avgStd = standardDeviation(validAverage);
        const maxMean = average(validMax) || 0;
        const maxStd = standardDeviation(validMax);

        filtered.forEach((item, index) => {
          if (
            item.resting_heart_rate != null &&
            item.resting_heart_rate > restingMean + Math.max(3, restingStd * 1.2)
          ) {
            anomalies.push(
              `${item.calendar_date}: resting HR ${item.resting_heart_rate} bpm`
            );
          }
          if (
            item.average_heart_rate != null &&
            item.average_heart_rate > avgMean + Math.max(5, avgStd * 1.25)
          ) {
            anomalies.push(
              `${item.calendar_date}: average HR ${item.average_heart_rate} bpm`
            );
          }
          if (
            item.max_heart_rate != null &&
            item.max_heart_rate > maxMean + Math.max(10, maxStd * 1.25)
          ) {
            anomalies.push(
              `${item.calendar_date}: max HR ${item.max_heart_rate} bpm`
            );
          }
          if (index > 0) {
            const previous = filtered[index - 1];
            if (
              item.resting_heart_rate != null &&
              previous.resting_heart_rate != null &&
              item.resting_heart_rate - previous.resting_heart_rate >= 5
            ) {
              anomalies.push(
                `${item.calendar_date}: resting HR jumped ${item.resting_heart_rate - previous.resting_heart_rate} bpm vs previous day`
              );
            }
          }
        });

        return Array.from(new Set(anomalies)).slice(0, 8);
      }

      function renderAnomalyList(container, items, emptyMessage) {
        if (!items.length) {
          container.innerHTML = `<li>${emptyMessage}</li>`;
          return;
        }
        container.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
      }

      function updateRangeSummary(filtered, hourlyProfile, trendData, activities, startValue, endValue) {
        if (!filtered.length) {
          rangeSummary.textContent = "No data in selected range.";
          rangePills.innerHTML = "";
          renderAnomalyList(rangeAnomalies, [], "No anomalies in selected range.");
          return;
        }
        const peakHour = hourlyProfile.length
          ? hourlyProfile.reduce((best, item) => (best == null || item.average > best.average ? item : best), null)
          : null;
        const lowHour = hourlyProfile.length
          ? hourlyProfile.reduce((best, item) => (best == null || item.average < best.average ? item : best), null)
          : null;
        const sampleCount = filtered.reduce((sum, item) => sum + item.sample_count, 0);
        const lines = [
          `date_range: ${startValue} .. ${endValue}`,
          `days_in_range: ${filtered.length}`,
          `wellness_samples: ${sampleCount}`,
          `trend_mode: ${aggregationSelect.value}`,
          `avg_resting_hr: ${restingValue.textContent}`,
          `avg_daily_hr: ${avgValue.textContent}`,
          `avg_daily_max_hr: ${maxValue.textContent}`,
        ];
        if (peakHour) {
          lines.push(`highest_hourly_avg: ${peakHour.label} (${peakHour.average} bpm)`);
        }
        if (lowHour) {
          lines.push(`lowest_hourly_avg: ${lowHour.label} (${lowHour.average} bpm)`);
        }
        rangeSummary.textContent = lines.join("\\n");
        rangePills.innerHTML = [
          `<span class="pill">Trend points: ${trendData.length}</span>`,
          `<span class="pill">Activities in range: ${activities.length}</span>`,
          `<span class="pill">Activity type: ${activityTypeSelect.value || "All"}</span>`
        ].join("");
        renderAnomalyList(
          rangeAnomalies,
          buildDailyAnomalies(filtered),
          "No standout daily anomalies in this range."
        );
      }

      function updateTrendChart(trendData) {
        trendChart.data.labels = trendData.map((item) => item.label);
        trendChart.data.datasets[0].data = trendData.map((item) => item.resting);
        trendChart.data.datasets[1].data = trendData.map((item) => item.average);
        trendChart.data.datasets[2].data = trendData.map((item) => item.maximum);
        trendChart.update();
      }

      function updateHourlyChart(hourlyProfile) {
        hourlyChart.data.labels = hourlyProfile.map((item) => item.label);
        hourlyChart.data.datasets[0].data = hourlyProfile.map((item) => item.average);
        hourlyChart.update();
      }

      function updateRunningTrendChart(runningTrend) {
        runningTrendChart.data.labels = runningTrend.map((item) => item.label);
        runningTrendChart.data.datasets[0].data = runningTrend.map((item) => item.average);
        runningTrendChart.data.datasets[1].data = runningTrend.map((item) => item.maximum);
        runningTrendChart.update();
      }

      function getFilteredActivities(startValue, endValue) {
        const selectedType = activityTypeSelect.value;
        return allActivities.filter(
          (item) =>
            item.calendar_date &&
            item.calendar_date >= startValue &&
            item.calendar_date <= endValue &&
            (!selectedType || item.activity_type === selectedType)
        );
      }

      function populateActivityTypeOptions() {
        const activityTypes = Array.from(
          new Set(allActivities.map((item) => item.activity_type).filter(Boolean))
        ).sort();
        activityTypeSelect.innerHTML = [
          `<option value="">All types</option>`,
          ...activityTypes.map((value) => `<option value="${value}">${value}</option>`)
        ].join("");
      }

      function updateActivityOptions(startValue, endValue) {
        const filtered = getFilteredActivities(startValue, endValue);
        activitySelect.innerHTML = "";
        if (!filtered.length) {
          const option = document.createElement("option");
          option.value = "";
          option.textContent = "No activity in range";
          activitySelect.appendChild(option);
          renderActivityDetail(null);
          return;
        }

        filtered.forEach((item, index) => {
          const option = document.createElement("option");
          option.value = String(item.activity_id);
          const label = [
            item.calendar_date,
            item.activity_name || "Unnamed activity",
            item.activity_type || ""
          ].filter(Boolean).join(" · ");
          option.textContent = label;
          if (index === filtered.length - 1) {
            option.selected = true;
          }
          activitySelect.appendChild(option);
        });
        renderSelectedActivity();
      }

      function renderActivityDetail(activity) {
        if (!activity) {
          activityMeta.innerHTML = "";
          activityChart.data.labels = [];
          activityChart.data.datasets[0].data = [];
          activityChart.data.datasets[1].data = [];
          activityChart.update();
          activityEmpty.style.display = "block";
          renderAnomalyList(activityAnomalies, [], "Select an activity to inspect detailed spikes.");
          return;
        }

        const labels = activity.samples.map((item) => item.timestamp_local.slice(11, 19));
        const bpmValues = activity.samples.map((item) => item.bpm);
        const mean = average(bpmValues) || 0;
        const std = standardDeviation(bpmValues);
        const anomalyThreshold = mean + Math.max(8, std * 2);
        const anomalyPoints = activity.samples
          .map((item, index) => ({
            x: labels[index],
            y: item.bpm,
            timestamp: item.timestamp_local
          }))
          .filter((item) => item.y >= anomalyThreshold);
        activityChart.data.labels = labels;
        activityChart.data.datasets[0].data = bpmValues;
        activityChart.data.datasets[1].data = anomalyPoints;
        activityChart.update();
        activityEmpty.style.display = activity.samples.length ? "none" : "block";

        activityMeta.innerHTML = [
          `<div><strong>${activity.activity_name || "Unnamed activity"}</strong></div>`,
          `<div>Date: ${activity.calendar_date || "n/a"}</div>`,
          `<div>Type: ${activity.activity_type || "n/a"}</div>`,
          `<div>Start: ${activity.start_time_local || "n/a"}</div>`,
          `<div>Duration: ${formatDuration(activity.duration_seconds)}</div>`,
          `<div>Distance: ${formatDistance(activity.distance_meters)}</div>`,
          `<div>Avg HR: ${activity.average_heart_rate ?? "n/a"}</div>`,
          `<div>Max HR: ${activity.max_heart_rate ?? "n/a"}</div>`,
          `<div>Samples: ${activity.sample_count ?? 0}</div>`,
          `<div>Spike threshold: ${anomalyThreshold.toFixed(1)} bpm</div>`
        ].join("");

        renderAnomalyList(
          activityAnomalies,
          anomalyPoints.slice(0, 8).map((item) => `${item.timestamp}: ${item.y} bpm`),
          "No standout spikes in this activity."
        );
      }

      function loadActivityData(activityMetaItem) {
        return new Promise((resolve, reject) => {
          if (!activityMetaItem) {
            resolve(null);
            return;
          }
          if (activityCache[activityMetaItem.activity_id]) {
            resolve(activityCache[activityMetaItem.activity_id]);
            return;
          }
          const script = document.createElement("script");
          script.src = activityMetaItem.data_path;
          script.onload = () =>
            resolve(window.__GARMIN_ACTIVITY_DATA__[activityMetaItem.activity_id] || null);
          script.onerror = () => reject(new Error(`Failed to load ${activityMetaItem.data_path}`));
          document.head.appendChild(script);
        });
      }

      async function renderSelectedActivity() {
        const activityId = Number(activitySelect.value);
        const activityMetaItem = allActivities.find((item) => item.activity_id === activityId);
        if (!activityMetaItem) {
          renderActivityDetail(null);
          return;
        }
        try {
          const activity = await loadActivityData(activityMetaItem);
          renderActivityDetail(activity);
        } catch (error) {
          activityMeta.innerHTML = `<div>${error.message}</div>`;
          renderActivityDetail(null);
        }
      }

      function renderRange() {
        const { startValue, endValue } = getSelectedRange();
        const filtered = filterSummaries(startValue, endValue);
        const hourlyProfile = buildHourlyProfile(startValue, endValue);
        const trendData = buildTrendData(filtered, aggregationSelect.value);
        const runningTrend = buildRunningTrendData(startValue, endValue, aggregationSelect.value);
        const activities = getFilteredActivities(startValue, endValue);
        updateSummaryCards(filtered);
        updateRangeSummary(filtered, hourlyProfile, trendData, activities, startValue, endValue);
        updateTrendChart(trendData);
        updateHourlyChart(hourlyProfile);
        updateRunningTrendChart(runningTrend);
        updateActivityOptions(startValue, endValue);
      }

      document.querySelectorAll("[data-preset]").forEach((button) => {
        button.addEventListener("click", () => updatePreset(button.dataset.preset));
      });
      startInput.addEventListener("change", renderRange);
      endInput.addEventListener("change", renderRange);
      aggregationSelect.addEventListener("change", renderRange);
      activityTypeSelect.addEventListener("change", renderRange);
      activitySelect.addEventListener("change", renderSelectedActivity);

      if (allSummaries.length) {
        populateActivityTypeOptions();
        updatePreset(28);
      }
    </script>
  </body>
</html>
"""

    DASHBOARD_HTML.write_text(html.replace("{asset_version}", asset_version), encoding="utf-8")


def maybe_render_charts(summaries: List[DailySummary], hourly_profile: Dict[int, float]) -> None:
    try:
        MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)
        import matplotlib

        matplotlib.use("Agg")
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
    daily_hourly_bins = load_daily_hourly_bins(conn)
    activities = load_activity_summaries(conn)
    running_daily_trend = load_running_daily_trend(conn)
    asset_version = datetime.now().strftime("%Y%m%d%H%M%S")

    write_summary_csv(summaries)
    write_text_summary(summaries, hourly_profile)
    write_dashboard_data(
        summaries,
        daily_hourly_bins,
        activities,
        running_daily_trend,
        asset_version,
        conn,
    )
    write_html_dashboard(asset_version)
    maybe_render_charts(summaries, hourly_profile)

    conn.close()

    print(f"Saved {SUMMARY_CSV}")
    print(f"Saved {SUMMARY_TXT}")
    print(f"Saved {DASHBOARD_HTML}")
    print(f"Saved {DASHBOARD_DATA_JS}")
    if TREND_PNG.exists():
        print(f"Saved {TREND_PNG}")
    if HOURLY_PNG.exists():
        print(f"Saved {HOURLY_PNG}")


if __name__ == "__main__":
    main()
