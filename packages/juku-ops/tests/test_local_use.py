"""Local-use mode (ops/local/): Arthur's own Juku on his Mac keeps its learners, and backs them up."""

import plistlib
import re
from pathlib import Path
from typing import Any, cast

import yaml
from juku_testkit.databases import repo_root

LOCAL = repo_root() / "ops" / "local"


def use_override() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load((LOCAL / "use.yaml").read_text(encoding="utf-8")))


def script() -> str:
    return (LOCAL / "juku.sh").read_text(encoding="utf-8")


def test_the_learners_database_is_on_a_volume_compose_cant_delete() -> None:
    # External: no `down -v`, recreate or project clean-up removes or orphans it, as it did the anonymous one.
    override = use_override()
    assert override["services"]["db"]["volumes"] == ["learner-data:/var/lib/postgresql/data"]
    assert override["volumes"]["learner-data"] == {"name": "juku-local-pgdata", "external": True}


def test_local_use_has_no_down() -> None:
    commands = re.findall(r"^(\S+)\) ", script(), re.MULTILINE)
    assert "down" not in commands
    assert {"start", "stop", "backup", "restore-check", "nightly"} <= set(commands)


def launch_agent(command: str, schedule_name: str) -> dict[str, Any]:
    """The LaunchAgent install_agent writes for `command`, with the schedule juku.sh names `schedule_name`."""
    found = re.search(rf"^{schedule_name}='(.*)'$", script(), re.MULTILINE)
    assert found, f"juku.sh has no {schedule_name}"
    template = (LOCAL / "launch-agent.plist").read_text(encoding="utf-8")
    filled = template.replace("@COMMAND@", command).replace("@SCHEDULE@", found.group(1))
    return cast(dict[str, Any], plistlib.loads(filled.encode()))


def test_the_nightly_job_backs_up_then_checks_the_restore() -> None:
    assert re.search(r"^nightly\) backup && restore_check ;;$", script(), re.MULTILINE)
    plist = launch_agent("nightly", "NIGHTLY_AT")
    assert plist["ProgramArguments"][-1] == "nightly"
    assert plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 0}


def test_the_weekly_runs_are_checked_every_hour_as_on_the_server() -> None:
    assert "run --rm --no-deps -T app juku run-weekly --due" in script()
    plist = launch_agent("weekly", "HOURLY")
    assert plist["ProgramArguments"][-1] == "weekly"
    assert plist["StartInterval"] == 3600


def test_backups_are_encrypted_and_kept_outside_the_repository() -> None:
    text = script()
    assert '| age -r "$(public_key)"' in text
    assert "BACKUPS=${JUKU_BACKUP_DIR:-$HOME/Backups/juku}" in text
    assert not Path(repo_root() / "Backups").exists()


def test_a_restore_check_compares_the_learners_data() -> None:
    assert '[[ $live == "$restored" ]]' in script()
