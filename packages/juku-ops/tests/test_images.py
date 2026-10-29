"""The images' virtual environments run where they were built (app/Dockerfile, packages/juku-mcp/Dockerfile).

uv writes each console script with the venv's absolute path in its first line (`#!/src/.venv/bin/python`).
A venv built in one folder and copied to another keeps those lines, so `juku serve` and `juku-mcp serve`,
the images' commands, fail with "no such file or directory". Found by the load test (FF10).
"""

import re
from pathlib import Path

import pytest
from juku_testkit.databases import repo_root

DOCKERFILES = ["app/Dockerfile", "packages/juku-mcp/Dockerfile"]
BUILD_STAGE = re.compile(r"^FROM \S+ AS build$(?P<stage>.*?)^FROM ", re.MULTILINE | re.DOTALL)
WORKDIR = re.compile(r"^WORKDIR (\S+)$", re.MULTILINE)
VENV_COPY = re.compile(r"^COPY --from=build (\S+) (\S+)$", re.MULTILINE)


def dockerfile(relative: str) -> str:
    path: Path = repo_root() / relative
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("relative", DOCKERFILES)
def test_the_venv_is_copied_to_the_folder_it_was_built_in(relative: str) -> None:
    text = dockerfile(relative)
    stage = BUILD_STAGE.search(text)
    copied = VENV_COPY.search(text)
    assert stage and copied, f"{relative}: no build stage, or no venv copied out of it"
    built_in = WORKDIR.findall(stage.group("stage"))[-1] + "/.venv"
    assert copied.groups() == (built_in, built_in)
