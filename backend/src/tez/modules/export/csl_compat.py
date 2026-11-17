"""Fixes for citeproc-py gaps that change what the bundled styles print (Task 39).

citeproc-py 0.12 is the only permissively licensed CSL processor for Python (ADR 0019), but it
does not implement all of CSL 1.0.2. These are the gaps the bundled styles hit, each covered by
an expected-output test, so a citeproc-py update that changes them shows up:

1. `initialize="false"` on `cs:name` is ignored, so MLA and Chicago shorten given names to
   initials ("Creswell, J. W." for "Creswell, John W.").
2. A `cs:group` counts a constant text inside a matching `cs:choose` branch as a rendered
   variable, so APA prints "(Publication)" for a thesis without a number.
3. Casing uses Python's rules, so Turkish terms come out as "Içinde" instead of "İçinde".
   Turkish rules apply to the locale's terms in a Turkish bibliography and to the text of
   Turkish items; an English title in a Turkish bibliography keeps English casing.
4. `punctuation-in-quote` is ignored: US English puts a period or comma inside the closing
   quote (“Grounded Theory.”). Fixed on the rendered text in `csl.py`.
5. `second-field-align` gives no gap after the citation number ("[1]A. Author"). Fixed in the
   style XML in `csl.py`.

citeproc-py has no type hints; this module and `csl.py` are the only places that touch it.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportUnknownParameterType=false
# pyright: reportMissingParameterType=false, reportMissingTypeStubs=false
# pyright: reportAttributeAccessIssue=false

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from citeproc import model, string
from citeproc.source import VariableError

# The bibliography being rendered is Turkish (its terms are Turkish).
_turkish_locale: ContextVar[bool] = ContextVar("tez_csl_turkish_locale", default=False)
# The text being cased right now is Turkish.
_turkish_case: ContextVar[bool] = ContextVar("tez_csl_turkish_case", default=False)
_installed = False


@contextmanager
def turkish_locale(enabled: bool) -> Generator[None]:
    """Mark the bibliography rendered inside as Turkish, for casing its terms."""
    token = _turkish_locale.set(enabled)
    try:
        yield
    finally:
        _turkish_locale.reset(token)


def _upper(text: str) -> str:
    if _turkish_case.get():
        text = text.replace("i", "İ")
    return text.upper()


def _lower(text: str) -> str:
    if _turkish_case.get():
        text = text.replace("I", "ı").replace("İ", "i")
    return text.lower()


def _string_upper(self: Any) -> Any:
    return self.__class__(_upper(str(self)))


def _string_lower(self: Any) -> Any:
    return self.__class__(_lower(str(self)))


def _string_capitalize_first(self: Any) -> Any:
    text = str(self)
    return self.__class__(_upper(text[:1]) + text[1:])


_original_case = model.TextCased.case


def _case(self: Any, text: Any, language: Any = None) -> Any:
    """Case a term by the bibliography's language and an item's text by the item's."""
    is_term = self.get("term") is not None or isinstance(self, model.Label)
    turkish = _turkish_locale.get() if is_term else language == "tr"
    token = _turkish_case.set(turkish)
    try:
        return _original_case(self, text, language)
    finally:
        _turkish_case.reset(token)


def _inherited_option(element: Any, context: Any, name: str) -> str | None:
    """A name option set on the element, else on the calling citation or bibliography, else
    on the style (CSL's inheritable name options)."""
    value = element.get(name)
    if value is not None:
        return value
    source = context if context is not None else element
    parents = source.xpath_search(
        "./ancestor-or-self::*[self::cs:citation or self::cs:bibliography][1]"
    )
    if parents and parents[0].get(name) is not None:
        return parents[0].get(name)
    return element.get_root().get(name)


_original_initialize = model.Name.initialize


def _initialize(self: Any, given: Any, mark: Any, context: Any) -> Any:
    if _inherited_option(self, context, "initialize") == "false":
        return given
    return _original_initialize(self, given, mark, context)


def _render_choose(choose: Any, item: Any, context: Any, delimiter: str, kwargs: Any) -> Any:
    """The text of the first matching branch and that branch (None, None when none matches)."""
    for branch in choose.getchildren():
        try:
            return branch.render(item, context=context, delimiter=delimiter, **kwargs), branch
        except model.ConditionFailed:
            continue
    return None, None


def _group_process(self: Any, item: Any, context: Any = None, **kwargs: Any) -> Any:
    """citeproc-py's `Group.process`, except that a `cs:choose` counts as rendering a variable
    only when the branch it took calls one."""
    output: list[Any] = []
    variable_called = False
    variable_rendered = False
    delimiter = self.get("delimiter", "")
    for child in self.iterchildren():
        variable_called = variable_called or child.calls_variable()
        try:
            if isinstance(child, model.Choose):
                child_text, branch = _render_choose(child, item, context, delimiter, kwargs)
                renders_variable = branch is not None and branch.calls_variable()
            else:
                child_text = child.render(item, context=context, **kwargs)
                renders_variable = child.calls_variable()
            if child_text is not None:
                output.append(child_text)
                variable_rendered = variable_rendered or renders_variable
        except VariableError:
            continue
    if output and (not variable_called or variable_rendered):
        return self.join(output)
    raise VariableError


def install() -> None:
    """Apply the fixes once per process."""
    global _installed
    if _installed:
        return
    string.String.upper = _string_upper
    string.String.lower = _string_lower
    string.String.capitalize_first = _string_capitalize_first
    model.TextCased.case = _case
    model.Name.initialize = _initialize
    model.Group.process = _group_process
    _installed = True
