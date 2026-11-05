"""Studying words in context (engine/study.py): examples, grammar points, a sentence explained, a kanji."""

from datetime import UTC, datetime

from juku_data.engine import (
    Databases,
    create_learner,
    explain_sentences,
    get_grammar_at_level,
    get_grammar_point,
    get_kanji,
    get_word,
    mark_known,
)
from sqlalchemy import text


async def word_id(db: Databases, word: str, reading: str) -> str:
    async with db.dictionary.connect() as connection:
        found = await connection.scalar(
            text("SELECT id FROM ojlpt.vocab WHERE word = :word AND reading = :reading"),
            {"word": word, "reading": reading},
        )
    assert isinstance(found, str), f"{word} isn't in the dictionary"
    return found


async def test_a_word_comes_with_examples_of_it_in_use(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="study-a", target_level=5)
    taberu = await word_id(engine_databases, "食べる", "たべる")
    entry = await get_word(engine_databases, learner.id, taberu)
    assert entry is not None and entry.level == 5 and "to eat" in entry.meanings
    assert 1 <= len(entry.examples) <= 5
    assert all(example.en for example in entry.examples)
    assert entry.is_known is False


async def test_an_unknown_word_has_no_page(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="study-b", target_level=5)
    assert await get_word(engine_databases, learner.id, "no-such-word") is None


async def test_the_grammar_points_of_a_level_come_in_openjlpts_order(engine_databases: Databases) -> None:
    points = await get_grammar_at_level(engine_databases, 5)
    assert len(points) == 81
    assert points[0].pattern == "〜は"
    assert {point.level for point in points} == {5}


async def test_a_grammar_point_explains_its_formation_with_examples(engine_databases: Databases) -> None:
    point = await get_grammar_point(engine_databases, "wa")
    assert point is not None and point.formation == "Noun + は"
    assert len(point.examples) == 3 and point.examples[0].furigana


async def test_a_sentence_is_explained_word_by_word_with_its_grammar(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="study-c", target_level=5)
    gakusei = await word_id(engine_databases, "学生", "がくせい")
    await mark_known(engine_databases, learner.id, gakusei, datetime.now(UTC))
    explained = await explain_sentences(engine_databases, learner.id, ["私は学生です。", "not an example"])
    assert list(explained) == ["私は学生です。"]
    sentence = explained["私は学生です。"]
    student = next(token for token in sentence.tokens if token.surface == "学生")
    assert student.kind == "word" and student.words[0].is_known
    assert [point.pattern for point in sentence.grammar] == ["〜です", "〜は"]


async def test_a_kanji_shows_its_readings_and_known_words_first(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="study-d", target_level=5)
    sensei = await word_id(engine_databases, "先生", "せんせい")
    await mark_known(engine_databases, learner.id, sensei, datetime.now(UTC))
    kanji = await get_kanji(engine_databases, learner.id, "生")
    assert kanji is not None and "セイ" in kanji.onyomi and "life" in kanji.meanings
    assert kanji.words[0].word == "先生" and kanji.words[0].is_known
    assert len(kanji.words) <= 8


async def test_a_character_that_isnt_a_jlpt_kanji_has_no_entry(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="study-e", target_level=5)
    assert await get_kanji(engine_databases, learner.id, "あ") is None
