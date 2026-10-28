"""Download the pinned OpenJLPT files and check them (CI, or a fresh server).

Only the pinned commit's files, from GitHub, and each is checked against
its recorded SHA-256 before it's kept: a file that doesn't match is
deleted and the fetch fails.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from juku_data.dictionary.pin import FILE_URLS, NOTICE_FILE, NOTICE_SHA256, SQLITE_FILE, SQLITE_SHA256
from juku_data.dictionary.source import DictionaryError, sha256_of

EXPECTED_SHA256 = {SQLITE_FILE: SQLITE_SHA256, NOTICE_FILE: NOTICE_SHA256}
DOWNLOAD_TIMEOUT_SECONDS = 60.0


async def fetch_dictionary(folder: Path, client: httpx.AsyncClient) -> list[Path]:
    """Download each pinned file into `folder`; return the paths, all checked."""
    folder.mkdir(parents=True, exist_ok=True)
    fetched: list[Path] = []
    for name, url in FILE_URLS.items():
        path = folder / name
        response = await client.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True)
        if response.status_code != httpx.codes.OK.value:
            raise DictionaryError(f"downloading {url} answered {response.status_code}")
        path.write_bytes(response.content)
        if sha256_of(path) != EXPECTED_SHA256[name]:
            path.unlink()
            raise DictionaryError(f"{url} didn't match its pinned SHA-256; nothing was kept")
        fetched.append(path)
    return fetched
