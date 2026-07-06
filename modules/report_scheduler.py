"""Configurable report schedules for daily, weekly, and monthly monitoring."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG_DIR = Path("data/config")
SCHEDULE_PATH = CONFIG_DIR / "report_schedules.json"


@dataclass
class ReportSchedule:
    schedule_id: str
    competitor: str
    period: str = "daily"
    question: str = "请生成标准化竞品态势简报"
    enabled: bool = True
    last_run_at: str = ""
    next_run_at: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def mark_run(self) -> None:
        now = datetime.now(timezone.utc)
        self.last_run_at = now.isoformat()
        delta = {"daily": 1, "weekly": 7, "monthly": 30}.get(self.period, 1)
        self.next_run_at = (now + timedelta(days=delta)).isoformat()


def load_report_schedules() -> list[ReportSchedule]:
    if not SCHEDULE_PATH.exists():
        save_report_schedules([])
    data = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    return [ReportSchedule(**item) for item in data]


def save_report_schedules(schedules: list[ReportSchedule]) -> Path:
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_PATH.write_text(
        json.dumps([asdict(schedule) for schedule in schedules], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SCHEDULE_PATH


def upsert_report_schedule(schedule: ReportSchedule) -> ReportSchedule:
    schedules = load_report_schedules()
    for idx, existing in enumerate(schedules):
        if existing.schedule_id == schedule.schedule_id:
            schedules[idx] = schedule
            save_report_schedules(schedules)
            return schedule
    schedules.append(schedule)
    save_report_schedules(schedules)
    return schedule
