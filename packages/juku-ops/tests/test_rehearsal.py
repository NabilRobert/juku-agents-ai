"""The laptop rehearsal (ops/rehearse.sh, slice 8) can't spend, changes nothing the server runs, and runs every job."""

import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import yaml
from juku_testkit.databases import repo_root

OPS = repo_root() / "ops"
# What the rehearsal may change on the server's own services: ordering, and the model's address.
CHANGES_ALLOWED = {"depends_on", "environment"}


def load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def rehearsal() -> dict[str, Any]:
    return load_yaml(OPS / "rehearsal" / "compose.yaml")


def rehearsal_settings() -> dict[str, str]:
    lines = (OPS / "rehearsal" / "rehearsal.env").read_text(encoding="utf-8").splitlines()
    pairs = [line.split("=", 1) for line in lines if line and not line.startswith("#")]
    return {name: value for name, value in pairs}


def test_the_model_is_unreachable_in_a_rehearsal() -> None:
    url = urlparse(rehearsal()["services"]["app"]["environment"]["JUKU_MODEL_BASE_URL"])
    assert url.hostname == "127.0.0.1"


def test_the_rehearsal_empties_the_model_key() -> None:
    script = (OPS / "rehearse.sh").read_text(encoding="utf-8")
    assert re.search(r"^\s*: >juku_model_api_key$", script, re.MULTILINE)


def test_the_rehearsal_changes_only_ordering_and_the_models_address_on_the_servers_services() -> None:
    server_services = set(load_yaml(OPS / "compose.yaml")["services"])
    for name, service in rehearsal()["services"].items():
        if name in server_services:
            assert set(service) <= CHANGES_ALLOWED, name


def test_the_stand_in_database_is_published_on_loopback_only() -> None:
    for port in rehearsal()["services"]["db"]["ports"]:
        assert str(port).startswith("127.0.0.1:")


def test_the_rehearsal_sets_every_setting_the_server_must_set() -> None:
    required = re.findall(r"\$\{(\w+):\?", (OPS / "compose.yaml").read_text(encoding="utf-8"))
    assert set(required) <= set(rehearsal_settings())


def test_the_rehearsal_runs_every_crontab_job_as_cron_does() -> None:
    # It runs the words after $JUKU_COMPOSE on each crontab line, so a job written another way would be skipped.
    script = (OPS / "rehearse.sh").read_text(encoding="utf-8")
    assert r"sed -n 's/^.*\$JUKU_COMPOSE //p' crontab" in script
    lines = (OPS / "crontab").read_text(encoding="utf-8").splitlines()
    jobs = [line for line in lines if line.strip() and not line.startswith("#") and "=" not in line.split()[0]]
    assert len(jobs) == 7
    assert all(" $JUKU_COMPOSE " in job for job in jobs)
