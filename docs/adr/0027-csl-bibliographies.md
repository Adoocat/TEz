# 0027 — Formatted bibliographies: bundled CSL styles, citeproc-py with a small fix layer

- **Status:** Accepted
- **Date:** 2026-11-17
- **Task:** 39 (formatted bibliography, CSL)

## Context

ADR 0019 settled that bibliographies are rendered in the backend with `citeproc-py` (BSD-2-Clause-Views), never with `citeproc-js` (AGPL/CPAL). Task 39 asks for at least APA 7, MLA, Chicago, Vancouver and IEEE, in Turkish and English, for selected papers, a collection or the studies included in a review.

We checked citeproc-py 0.12.3 (November 2026). It installs and runs on Python 3.12 and 3.13 (its classifiers list 3.11–3.15), depends only on `lxml` (BSD-3-Clause) and ships the CSL locales, `tr-TR` and `en-US` included. It renders all the needed styles, but it gets some things wrong:

1. It ignores `initialize="false"`, so MLA and Chicago print "Creswell, J. W." instead of "Creswell, John W.".
2. A group counts a constant text in a `cs:choose` branch as a rendered variable, so APA prints "(Publication)" for a thesis without a number.
3. It uses Python's casing, so Turkish terms read "Içinde" instead of "İçinde".
4. It ignores `punctuation-in-quote`, so US English prints “Grounded Theory”. instead of “Grounded Theory.”
5. It prints no gap after the number of numbered styles ("[1]A. Author").
6. Its HTML output passes field text through as markup (a title "Q&A <tags>" comes out unescaped).

There is no other permissively licensed CSL processor for Python. The owner chose to keep citeproc-py and fix these gaps in our code (2026-11-14).

## Decision

- **Styles are bundled, unchanged,** from the CSL repository (CC BY-SA 3.0, attributed in `docs/licenses.md`): `apa`, `modern-language-association`, `chicago-author-date`, `chicago-notes-bibliography`, `nlm-citation-sequence` (Vancouver) and `ieee`. Both Chicago variants are offered. Locales come from citeproc-py.
- **`modules/export/csl_compat.py`** fixes gaps 1–3 by replacing three citeproc-py methods once per process. `csl.py` fixes 4 and 5 (on the rendered text, and on the style XML in memory) and 6 (field text is HTML-escaped before the HTML pass). citeproc-py is pinned to `<0.13`, because the fixes depend on its internals; the expected-output tests cover every fix, so an update that breaks one fails the tests.
- **Turkish casing** applies to the locale's terms in a Turkish bibliography and to the text of Turkish items, so an English title in a Turkish list still reads "Insight", not "İnsight".
- **Title case is for English items only** (the CSL rule). A paper whose language is unknown is taken to be in the bibliography's language: a Turkish list leaves its titles as they are, an English list title-cases them. This keeps "Eğitim ve Bilim" from becoming "Eğitim Ve Bilim" when a record has no language.
- **Thesis degree** (Task 28) goes into CSL `genre`, in the bibliography's language ("Yüksek lisans tezi", "Doctoral dissertation").
- **API:** `POST /export/bibliography` with a style, a locale and one scope: `paper_ids`, `collection_id`, `review_id` (its studies included at full text, read through `ScreeningService.included`), or none for the whole library. The answer has each entry as inline HTML and plain text, and the whole list both ways (one `<p>` per entry, so it pastes into Word with its formatting). Papers go in by citation key; author-date styles sort themselves, numbered styles keep that order.

## Consequences

- The fixes are ours to keep while citeproc-py has these gaps; they are worth reporting upstream.
- Our data has no editors, publisher place or edition, so chapters print without editors and books without place. The styles handle missing fields themselves.
- An English paper with no language in a Turkish list is not title-cased in MLA or Chicago. Setting the paper's language fixes it.
- Institute thesis styles can later be added as more bundled or user-supplied CSL files.
- New dependencies: `citeproc-py` 0.12 (BSD-2-Clause-Views) and `lxml` 6.1 (BSD-3-Clause; libxml2 and libxslt are MIT).
