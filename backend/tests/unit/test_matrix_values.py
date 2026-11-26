"""Task 51: what a matrix cell holds and how it is converted when its column's type changes."""

import pytest

from tez.modules.matrix.values import (
    Cell,
    DataType,
    InvalidValue,
    Option,
    Words,
    check,
    convert,
    labels_in,
    parse,
    render,
)

T, N, E, M, B = (
    DataType.TEXT,
    DataType.NUMBER,
    DataType.ENUM,
    DataType.MULTI_ENUM,
    DataType.BOOL,
)
SURVEY, INTERVIEW = Option(id="o1", label="Anket"), Option(id="o2", label="Görüşme")
METHODS = [SURVEY, INTERVIEW]


@pytest.mark.parametrize(
    ("data_type", "value", "stored"),
    [
        (T, "  Nitel  ", "Nitel"),
        (T, "   ", None),
        (N, 12.0, 12),
        (N, 0.5, 0.5),
        (B, False, False),
        (E, "o2", "o2"),
        (M, ["o2", "o1"], ["o1", "o2"]),
        (M, [], None),
        (T, None, None),
    ],
)
def test_check_keeps_what_fits(data_type: DataType, value: object, stored: object) -> None:
    assert check(data_type, value, METHODS) == stored


@pytest.mark.parametrize(
    ("data_type", "value"),
    [
        (T, 3),
        (N, "3"),
        (N, True),
        (N, float("nan")),
        (B, "yes"),
        (E, "o9"),
        (M, ["o1", "o1"]),
        (M, "o1"),
    ],
)
def test_check_refuses_what_does_not_fit(data_type: DataType, value: object) -> None:
    with pytest.raises(InvalidValue):
        check(data_type, value, METHODS)


@pytest.mark.parametrize(
    ("text", "number"),
    [("42", 42), ("-3,5", -3.5), ("0.125", 0.125), ("2.5", 2.5), ("1 200", 1200)],
)
def test_numbers_are_read_in_both_notations(text: str, number: float) -> None:
    assert parse(N, text, []) == number


@pytest.mark.parametrize("text", ["1.420", "12,345", "n = 30", "30 kişi", "", "1e3"])
def test_numbers_are_not_guessed(text: str) -> None:
    # "1.420" is 1420 in Turkish and 1.42 in English: left as text, never guessed.
    assert parse(N, text, []) is None


@pytest.mark.parametrize(
    ("text", "value"),
    [("Evet", True), ("HAYIR", False), ("yes", True), ("Yok", False), ("x", True), ("belki", None)],
)
def test_yes_and_no_in_turkish_and_english(text: str, value: bool | None) -> None:
    assert parse(B, text, []) == value


def test_choices_are_matched_by_label_turkish_letters_folded() -> None:
    assert parse(E, "GÖRÜŞME", METHODS) == "o2"
    assert parse(M, "görüşme; ANKET", METHODS) == ["o1", "o2"]
    assert parse(M, "Anket; Gözlem", METHODS) is None


def test_render_writes_values_as_a_person_would() -> None:
    assert render(N, 3.0, [], Words()) == "3"
    assert render(B, True, [], Words(true="Evet", false="Hayır")) == "Evet"
    assert render(M, ["o1", "o2"], METHODS, Words()) == "Anket; Görüşme"


def test_labels_in_finds_each_choice_once() -> None:
    texts = ["Anket", "anket", "Görüşme; Anket", " "]
    assert labels_in(texts, multi=False) == ["Anket", "Görüşme; Anket"]
    assert labels_in(texts, multi=True) == ["Anket", "Görüşme"]


# --- conversion: nothing is lost without a word ----------------------------------------------


def test_text_to_number_keeps_what_it_cannot_read() -> None:
    old, new = (T, []), (N, [])
    assert convert(Cell("120"), old, new) == Cell(120)
    assert convert(Cell("1.420"), old, new) == Cell(None, kept_text="1.420")
    assert convert(Cell("about 30"), old, new) == Cell(None, kept_text="about 30")


def test_kept_text_comes_back_whole_and_is_tried_again() -> None:
    kept = Cell(None, kept_text="about 30")
    assert convert(kept, (N, []), (T, [])) == Cell("about 30")
    assert convert(Cell(None, kept_text="30"), (N, []), (N, [])) == Cell(30)


def test_a_renamed_option_keeps_its_cells() -> None:
    renamed = [Option(id="o1", label="Survey"), INTERVIEW]
    assert convert(Cell("o1"), (E, METHODS), (E, renamed)) == Cell("o1")


def test_a_removed_option_leaves_its_label_as_text() -> None:
    assert convert(Cell("o1"), (E, METHODS), (E, [INTERVIEW])) == Cell(None, kept_text="Anket")


def test_one_choice_and_several() -> None:
    assert convert(Cell("o1"), (E, METHODS), (M, METHODS)) == Cell(["o1"])
    assert convert(Cell(["o2"]), (M, METHODS), (E, METHODS)) == Cell("o2")
    both = convert(Cell(["o1", "o2"]), (M, METHODS), (E, METHODS))
    assert both == Cell(None, kept_text="Anket; Görüşme")


def test_yes_no_becomes_text_in_the_users_words() -> None:
    words = Words(true="Evet", false="Hayır")
    assert convert(Cell(False), (B, []), (T, []), words) == Cell("Hayır")
    assert convert(Cell("Hayır"), (T, []), (B, []), words) == Cell(False)


def test_a_round_trip_loses_nothing() -> None:
    texts = ["12", "1.420", "Anket", "n/a", "Evet"]
    cells = [Cell(text) for text in texts]
    for target in (N, E):
        options = METHODS if target == E else []
        there = [convert(cell, (T, []), (target, options)) for cell in cells]
        back = [convert(cell, (target, options), (T, [])) for cell in there]
        assert back == [Cell(text) for text in texts]
    # Yes/no comes back in the words it is written in.
    there = [convert(cell, (T, []), (B, [])) for cell in cells]
    back = [convert(cell, (B, []), (T, []), Words("Evet", "Hayır")) for cell in there]
    assert [cell.value for cell in back] == ["12", "1.420", "Anket", "n/a", "Evet"]
