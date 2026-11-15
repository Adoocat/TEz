"""The user's boolean query, and how each source wants to hear it.

Users write one query: `"code review" AND (LLM OR GPT) NOT survey`. Each source has its own
syntax, and some have no boolean logic at all. The translated form is stored per source on
`search_run.translated_query`, because reporting standards ask for the exact query per database.

Parsing never fails. A query is free text from a person, so unbalanced parentheses and dangling
operators are dropped rather than reported.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto


class Kind(Enum):
    TERM = auto()
    PHRASE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    OPEN = auto()
    CLOSE = auto()


@dataclass(frozen=True)
class Token:
    kind: Kind
    text: str = ""


_OPERANDS = (Kind.TERM, Kind.PHRASE)
# PubMed field tags: [MeSH], [MeSH Terms], [tiab], [au], [Title/Abstract].
_FIELD_TAG_SPACED = re.compile(r"\[[A-Za-z:/ ]+\]")
# Not whitespace to the scanner (a no-break space would be).
_HELD_SPACE = "\u2063"
_FIELD_TAG = re.compile(r"\[[A-Za-z:/\u2063]+\]")
# A tag written against its term: `asthma[tiab]`.
_GLUED_TAG = re.compile(r"(.+?)\[([A-Za-z:/\u2063]+)\]")
_OPERATORS = {"AND": Kind.AND, "OR": Kind.OR, "NOT": Kind.NOT}
_TOKEN = re.compile(r'"(?P<phrase>[^"]*)"?|(?P<open>\()|(?P<close>\))|(?P<word>[^\s()"]+)')


def _scan(query: str) -> list[Token]:
    tokens: list[Token] = []
    for match in _TOKEN.finditer(query):
        if match["open"]:
            tokens.append(Token(Kind.OPEN))
        elif match["close"]:
            tokens.append(Token(Kind.CLOSE))
        elif match["word"]:
            # Operators count only in capitals, so a title word like "or" stays a word.
            word = match["word"]
            kind = _OPERATORS.get(word)
            tokens.append(Token(kind) if kind else Token(Kind.TERM, word))
        elif phrase := " ".join((match["phrase"] or "").split()):
            tokens.append(Token(Kind.PHRASE, phrase))
    return tokens


def _balance(tokens: list[Token]) -> list[Token]:
    """Drop parentheses that have no partner."""
    unmatched: set[int] = set()
    opened: list[int] = []
    for index, token in enumerate(tokens):
        if token.kind is Kind.OPEN:
            opened.append(index)
        elif token.kind is Kind.CLOSE:
            if opened:
                opened.pop()
            else:
                unmatched.add(index)
    unmatched.update(opened)
    return [token for index, token in enumerate(tokens) if index not in unmatched]


def _tidy(tokens: list[Token]) -> list[Token]:
    """One pass of clean-up: dangling operators, empty groups, implicit AND."""
    tidy: list[Token] = []
    for token in tokens:
        previous = tidy[-1].kind if tidy else None
        ends_operand = previous in (*_OPERANDS, Kind.CLOSE)
        match token.kind:
            case Kind.AND | Kind.OR:
                if ends_operand:
                    tidy.append(token)
            case Kind.NOT:
                # "a AND NOT b" and "a NOT b" mean the same; NOT also implies AND.
                if previous is Kind.AND:
                    tidy.pop()
                if previous is not Kind.NOT:
                    tidy.append(token)
            case Kind.CLOSE:
                while tidy and tidy[-1].kind in (Kind.AND, Kind.OR, Kind.NOT):
                    tidy.pop()
                if tidy and tidy[-1].kind is Kind.OPEN:
                    tidy.pop()  # An empty group.
                else:
                    tidy.append(token)
            case _:
                if ends_operand:
                    tidy.append(Token(Kind.AND))
                tidy.append(token)
    while tidy and tidy[-1].kind in (Kind.AND, Kind.OR, Kind.NOT, Kind.OPEN):
        tidy.pop()
    return tidy


def parse(query: str) -> list[Token]:
    """A well-formed token list: balanced, no dangling operators, every AND explicit."""
    tokens = _balance(_scan(query))
    while True:
        tidied = _balance(_tidy(tokens))
        if tidied == tokens:
            return tokens
        tokens = tidied


def without_negated(tokens: list[Token], *, only_without_left_side: bool = False) -> list[Token]:
    """Remove each NOT together with what it negates, for sources that cannot express it.

    With `only_without_left_side`, a NOT stays when it has something to subtract from.
    """
    kept: list[Token] = []
    depth = 0
    skip_until_depth: int | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token.kind is Kind.OPEN:
            depth += 1
        elif token.kind is Kind.CLOSE:
            depth -= 1
        if skip_until_depth is not None:
            if depth == skip_until_depth:
                skip_until_depth = None
            continue
        has_left_side = bool(kept) and kept[-1].kind is not Kind.OPEN
        if token.kind is not Kind.NOT or (only_without_left_side and has_left_side):
            kept.append(token)
            continue
        negated = tokens[index]
        index += 1
        if negated.kind is Kind.OPEN:
            skip_until_depth = depth
            depth += 1
    return parse(_render_plain(kept))


def _render_plain(tokens: list[Token]) -> str:
    return " ".join(_plain(token) for token in tokens)


def _plain(token: Token) -> str:
    match token.kind:
        case Kind.TERM:
            return token.text
        case Kind.PHRASE:
            return f'"{token.text}"'
        case Kind.AND | Kind.OR | Kind.NOT:
            return token.kind.name
        case Kind.OPEN:
            return "("
        case Kind.CLOSE:
            return ")"


def _join(parts: list[str]) -> str:
    """Join with single spaces, but keep parentheses tight against their contents."""
    return " ".join(parts).replace("( ", "(").replace(" )", ")")


def to_openalex(query: str) -> str:
    """OpenAlex `search=` understands capital AND/OR/NOT, quotes and parentheses."""
    return _join([_plain(token) for token in parse(query)])


def to_semantic_scholar(query: str) -> str:
    """Bulk search: a space is AND, `|` is OR, `-` excludes, plus quotes and parentheses."""
    parts: list[str] = []
    negate = False
    for token in parse(query):
        if token.kind is Kind.AND:
            continue
        if token.kind is Kind.OR:
            parts.append("|")
        elif token.kind is Kind.NOT:
            negate = True
        else:
            parts.append(("-" if negate else "") + _plain(token))
            negate = False
    return _join(parts)


def to_arxiv(query: str) -> str:
    """`all:` searches every field. ANDNOT needs a left side; a NOT without one is dropped."""
    parts: list[str] = []
    for token in without_negated(parse(query), only_without_left_side=True):
        match token.kind:
            case Kind.TERM | Kind.PHRASE:
                parts.append(f"all:{_plain(token)}")
            case Kind.NOT:
                parts.append("ANDNOT")
            case _:
                parts.append(_plain(token))
    return _join(parts)


def _tagged(query: str) -> list[tuple[str, str | None]]:
    """The query's parts, each with the PubMed field tag written after it (`[MeSH]`), if any."""
    # Spaces inside a tag would split it into two words: hold them until the end.
    held = _FIELD_TAG_SPACED.sub(lambda m: m.group(0).replace(" ", _HELD_SPACE), query)
    parts: list[tuple[str, str | None]] = []
    for token in parse(held):
        text = _plain(token)
        if token.kind is Kind.TERM and _FIELD_TAG.fullmatch(text) and parts:
            if parts[-1][0] == "AND" and len(parts) > 1:
                parts.pop()  # the AND the parser put between a term and its tag
            parts[-1] = (parts[-1][0], text[1:-1].replace(_HELD_SPACE, " "))
        elif token.kind is Kind.TERM and (glued := _GLUED_TAG.fullmatch(text)):
            parts.append((glued.group(1), glued.group(2).replace(_HELD_SPACE, " ")))
        else:
            parts.append((text, None))
    return parts


def to_pubmed(query: str) -> str:
    """PubMed takes AND/OR/NOT, quotes and parentheses as they are. A field tag the user wrote
    after a term or phrase stays attached to it: `"Neoplasms"[MeSH Terms]`, `asthma [tiab]`."""
    return _join([f"{text}[{tag}]" if tag else text for text, tag in _tagged(query)])


# PubMed tags Europe PMC has a field for; any other tag is dropped and its term searched as is.
_EUROPEPMC_FIELDS = {
    "mesh": "MESH",
    "mh": "MESH",
    "mesh terms": "MESH",
    "majr": "MESH",
    "ti": "TITLE",
    "title": "TITLE",
    "tiab": "TITLE_ABS",
    "title/abstract": "TITLE_ABS",
    "au": "AUTH",
    "author": "AUTH",
    "ta": "JOURNAL",
    "journal": "JOURNAL",
}


def to_europepmc(query: str) -> str:
    """Europe PMC takes AND/OR/NOT, quotes and parentheses, and fields as `FIELD:term`: a
    PubMed tag becomes its field (`"Neoplasms"[MeSH]` → `MESH:"Neoplasms"`)."""
    parts: list[str] = []
    for text, tag in _tagged(query):
        field = _EUROPEPMC_FIELDS.get(tag.lower()) if tag else None
        parts.append(f"{field}:{text}" if field else text)
    return _join(parts)


def to_keywords(query: str) -> str:
    """Plain words, for sources without boolean logic. Exclusions cannot be expressed."""
    return " ".join(
        token.text for token in without_negated(parse(query)) if token.kind in _OPERANDS
    )
