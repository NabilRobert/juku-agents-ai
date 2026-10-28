"""Write tests/fixtures/expected/<learner>.json from the oracle (tests/oracle.py), never from the engine.

Run it only when a rule in ADR-010 or LE4 changes, and commit the new
files in the same commit as the rule, with the reason (standard checks,
"recommender or engine rules").

Usage, with JUKU_DICT_DATABASE_URL pointing at a loaded dict database:
    uv run python packages/juku-data/tests/fixtures/regenerate_expected.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixture_learners import EXPECTED, FIXTURE_NAMES, known_words, load_fixture
from oracle import load_oracle_dictionary, reading_sentences, recommend
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    engine = create_async_engine(os.environ["JUKU_DICT_DATABASE_URL"])
    try:
        dictionary = await load_oracle_dictionary(engine)
        for name in FIXTURE_NAMES:
            fixture = await load_fixture(engine, name)
            known = known_words(fixture)
            expected = {
                "known_words": len(known),
                "recommendations": recommend(dictionary, known, fixture.target_level),
                "reading_sentences": reading_sentences(dictionary, known),
            }
            path = EXPECTED / f"{name}.json"
            path.write_text(json.dumps(expected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(f"{path.name}: {len(known)} known words")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
