"""Finding the pinned OpenJLPT files on disk and proving they're the pinned ones."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from juku_data.dictionary.pin import NOTICE_FILE, NOTICE_SHA256, OPENJLPT_COMMIT, SQLITE_FILE, SQLITE_SHA256

CHUNK_BYTES = 1 << 20


class DictionaryError(Exception):
    """The dictionary files are missing, changed, or failed to load. The message says what to do."""


@dataclass(frozen=True)
class SourceFiles:
    sqlite_path: Path
    notice_path: Path
    sqlite_sha256: str


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _check(path: Path, expected: str) -> str:
    if not path.is_file():
        raise DictionaryError(f"{path} is missing: fetch it with `juku-data fetch-dictionary --to {path.parent}`")
    actual = sha256_of(path)
    if actual != expected:
        raise DictionaryError(
            f"{path.name}'s SHA-256 is {actual}, not the pinned {expected} (OpenJLPT {OPENJLPT_COMMIT[:7]}): "
            "the file is corrupt or from another build. Fetch it again with `juku-data fetch-dictionary`."
        )
    return actual


def verify_source(
    folder: Path, *, expected_sqlite_sha256: str = SQLITE_SHA256, expected_notice_sha256: str = NOTICE_SHA256
) -> SourceFiles:
    """The files in `folder`, once both checksums match the pin."""
    sqlite_path, notice_path = folder / SQLITE_FILE, folder / NOTICE_FILE
    sqlite_sha256 = _check(sqlite_path, expected_sqlite_sha256)
    _check(notice_path, expected_notice_sha256)
    return SourceFiles(sqlite_path=sqlite_path, notice_path=notice_path, sqlite_sha256=sqlite_sha256)
