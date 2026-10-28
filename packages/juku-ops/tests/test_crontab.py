"""ops/crontab and monitoring.expected_jobs agree, so the "missed run" alert watches what cron runs."""

import re
from datetime import timedelta
from pathlib import Path

from juku_testkit.databases import repo_root
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

JOB = re.compile(r"juku-ops (?P<job>[a-z-]+)")
HEARTBEAT = "heartbeat"  # its staleness is the heartbeats row itself, not a job run


def period_of(minute: str, hour: str) -> timedelta:
    """The interval of the cron forms Juku uses: every minute, every N minutes, hourly, daily."""
    if (minute, hour) == ("*", "*"):
        return timedelta(minutes=1)
    if minute.startswith("*/") and hour == "*":
        return timedelta(minutes=int(minute[2:]))
    if minute.isdigit() and hour == "*":
        return timedelta(hours=1)
    if minute.isdigit() and hour.isdigit():
        return timedelta(days=1)
    raise ValueError(f"an unfamiliar schedule {minute} {hour}: extend period_of")


def scheduled_jobs(crontab: Path) -> dict[str, timedelta]:
    jobs: dict[str, timedelta] = {}
    for line in crontab.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" in line.split()[0]:
            continue
        minute, hour, *_ = line.split()
        found = JOB.search(line)
        if found and found["job"] != HEARTBEAT:
            jobs[found["job"]] = period_of(minute, hour)
    return jobs


async def test_every_scheduled_job_is_expected_with_the_same_period(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as connection:
        rows = (await connection.execute(text("SELECT job, every FROM monitoring.expected_jobs"))).all()
    expected = {str(job): every for job, every in rows}
    assert scheduled_jobs(repo_root() / "ops" / "crontab") == expected


def test_the_heartbeat_runs_every_minute() -> None:
    lines = (repo_root() / "ops" / "crontab").read_text(encoding="utf-8").splitlines()
    heartbeat_lines = [line for line in lines if line.endswith("juku-ops heartbeat")]
    assert [line.split()[:2] for line in heartbeat_lines] == [["*", "*"]]
