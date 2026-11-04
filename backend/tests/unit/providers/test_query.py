"""Query translation: one user query, each source's dialect, and no query that can crash it."""

import pytest

from tez.modules.search.providers.query import (
    to_arxiv,
    to_keywords,
    to_openalex,
    to_semantic_scholar,
)

BOOLEAN = '"code review" AND (LLM OR GPT) NOT survey'


def test_openalex_keeps_boolean_syntax() -> None:
    assert to_openalex(BOOLEAN) == '"code review" AND (LLM OR GPT) NOT survey'


def test_semantic_scholar_uses_its_own_operators() -> None:
    assert to_semantic_scholar(BOOLEAN) == '"code review" (LLM | GPT) -survey'


def test_arxiv_prefixes_every_term() -> None:
    assert to_arxiv(BOOLEAN) == 'all:"code review" AND (all:LLM OR all:GPT) ANDNOT all:survey'


def test_keywords_keep_words_and_drop_what_is_excluded() -> None:
    assert to_keywords(BOOLEAN) == "code review LLM GPT"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("code review", "code AND review"),
        ("kod inceleme ÇALIŞMA", "kod AND inceleme AND ÇALIŞMA"),
        ("a or b", "a AND or AND b"),  # Only capitals are operators.
        ("a AND NOT b", "a NOT b"),
        ("a NOT NOT b", "a NOT b"),
        ('"  spaced   phrase "', '"spaced phrase"'),
        ('"unclosed phrase', '"unclosed phrase"'),
        ('""', ""),
        ("", ""),
        ("   ", ""),
        ("AND", ""),
        ("AND a", "a"),
        ("a OR", "a"),
        ("a AND OR b", "a AND b"),
        ("(", ""),
        (")", ""),
        ("()", ""),
        ("((a)", "(a)"),
        ("(a))", "(a)"),
        (")a(", "a"),
        ("(a OR)", "(a)"),
        ("a () b", "a AND b"),
        ("(a) (b)", "(a) AND (b)"),
        ("NOT a", "NOT a"),
    ],
)
def test_messy_queries_are_cleaned_up_not_rejected(query: str, expected: str) -> None:
    assert to_openalex(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # Searching for "a" here would return the opposite of what the user asked for.
        ("NOT a", ""),
        ("NOT a b", "all:b"),
        ("NOT (a OR b) c", "all:c"),
        ("(NOT a) b", "all:b"),
        ("a NOT (b OR c)", "all:a ANDNOT (all:b OR all:c)"),
        ("a", "all:a"),
    ],
)
def test_arxiv_has_no_leading_not(query: str, expected: str) -> None:
    assert to_arxiv(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("NOT a", ""),
        ("a NOT (b OR c) d", "a d"),
        ("a NOT b", "a"),
        ("(a NOT b) c", "a c"),
    ],
)
def test_keywords_drop_negated_groups(query: str, expected: str) -> None:
    assert to_keywords(query) == expected


def test_semantic_scholar_negates_groups() -> None:
    assert to_semantic_scholar("a NOT (b OR c)") == "a -(b | c)"
