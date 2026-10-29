"""AG5 and Q2: every ID an answer cites must be among the rows its tools returned in that turn."""

from juku_app.citations import check_citations

RESULTS = [
    {"words": [{"word_id": "86f67e2dc3", "word": "食べる"}, {"word_id": "e0bcec9bd9", "word": "飲む"}]},
    {"sentences": [{"sentence_id": 1781, "new_word_id": "537f8af3d6"}]},
]


def test_an_answer_citing_returned_rows_is_verified() -> None:
    check = check_citations("食べる [ref:86f67e2dc3] dan 一つ [ref:537f8af3d6], kalimat [ref:1781].", RESULTS)
    assert (check.is_verified, check.unknown) == (True, ())
    assert check.cited == ("86f67e2dc3", "537f8af3d6", "1781")


def test_a_fabricated_citation_is_flagged() -> None:
    check = check_citations("見る [ref:85b37b6884] artinya melihat.", RESULTS)
    assert (check.is_verified, check.unknown) == (False, ("85b37b6884",))


def test_an_answer_with_facts_but_no_citation_is_not_verified() -> None:
    assert not check_citations("食べる artinya makan.", RESULTS).is_verified


def test_an_answer_saying_the_data_has_nothing_needs_no_citation() -> None:
    assert check_citations("Maaf, tidak ada di data.", []).is_verified
