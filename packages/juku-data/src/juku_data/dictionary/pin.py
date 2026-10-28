"""The one OpenJLPT build Juku uses, and how to check a download is it (ADR-003).

The data Juku needs (JMdict links, 526 grammar points) exists only on
OpenJLPT's `main`, not in a release, so Juku pins a commit and the SHA-256
of its files (spike 1). Arthur approved this commit on 2026-10-28. Moving to
a newer one is a reviewed change to this file, followed by a reload whose
report lists any word ID that disappeared.
"""

OPENJLPT_COMMIT = "bf4e1eecd5d11406aaecdee910464507aef7fcdc"
OPENJLPT_COMMIT_DATE = "2026-09-30"
SQLITE_FILE = "openjlpt.sqlite"
NOTICE_FILE = "NOTICE.md"
SQLITE_SHA256 = "5263ba7a5000a9013baa646b3b80241161028fc561c092d57dc8b864ae92b271"
NOTICE_SHA256 = "a2e6f45517bb1a1c047628991832244916888a4ced3aa26adeafb89705588557"
RAW_BASE_URL = f"https://raw.githubusercontent.com/evanclan/OpenJLPT/{OPENJLPT_COMMIT}"
FILE_URLS = {SQLITE_FILE: f"{RAW_BASE_URL}/data/{SQLITE_FILE}", NOTICE_FILE: f"{RAW_BASE_URL}/{NOTICE_FILE}"}

# Row counts of this build, as spike 1 recorded them. A load that doesn't
# reproduce them is a partial or wrong load.
EXPECTED_ROW_COUNTS = {"vocab": 7811, "vocab_example": 13718, "kanji": 2383, "grammar": 526, "pos": 47}
# Spike 1's md5 of each table's rows (spikes/1-dictionary-load/openjlpt/results-load.txt).
# A fresh load must give the same, row for row.
EXPECTED_TABLE_MD5 = {
    "grammar": "b9dce9d177cb9927730910444f486e1d",
    "kanji": "d9faaf3f43b5433d8c167a8b802cd33b",
    "pos": "75893ae291985d904121018249473c78",
    "vocab": "f13b1e8442b1e32950e5894d64dada37",
    "vocab_example": "40a32170f38a26f90b59f969fe3a103e",
}
