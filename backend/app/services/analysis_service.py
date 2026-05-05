"""Analysis orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class AnalysisService:
    def recompute_window(self, *, start_date: date, end_date: date) -> dict[str, object]:
        return {
            "start_date": start_date,
            "end_date": end_date,
            "todo": [
                "compute rolling baselines",
                "detect anomalies",
                "detect change points",
                "link events to metric segments",
                "persist insight records",
            ],
        }
