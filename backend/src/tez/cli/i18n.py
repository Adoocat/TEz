"""The CLI's words in Turkish and English (plan: human output in the system language; `--json`
field names are always English).

The language is fixed before the commands are built, so `--help` itself is translated: from
`--lang`, then `TEZ_LANG`, then the system's language, else English.
"""

import ctypes
import locale
import os
import sys
from collections.abc import Sequence
from typing import Any, Literal

Language = Literal["tr", "en"]

_WINDOWS_TURKISH = 0x1F  # primary language id of LANGID tr-TR

MESSAGES: dict[str, dict[Language, str]] = {
    # --- help ---------------------------------------------------------------------------
    "help.app": {
        "tr": "TEz terminal komutları: arama, içe aktarma, PDF ekleme, dışa aktarma.\n\n"
        "Kütüphane bir pencerede açıksa komutlar o pencerenin üzerinden çalışır ve sonuç "
        "orada da görünür; değilse kütüphane doğrudan açılır.",
        "en": "TEz in the terminal: search, import, add PDFs, export.\n\n"
        "If the library is open in a window, commands go through it and their results show "
        "there too; otherwise the library is opened directly.",
    },
    "help.library": {
        "tr": "Kütüphane klasörü (varsayılan: TEZ_LIBRARY ya da Belgeler/TEz Library).",
        "en": "Library folder (default: TEZ_LIBRARY, or Documents/TEz Library).",
    },
    "help.json": {
        "tr": "Betikler için kararlı JSON çıktısı (alan adları İngilizce).",
        "en": "Stable JSON output for scripts (English field names).",
    },
    "help.lang": {"tr": "Çıktı dili: tr veya en.", "en": "Output language: tr or en."},
    "help.quiet": {"tr": "Yalnızca hataları yaz.", "en": "Print errors only."},
    "help.search": {
        "tr": "Kaynaklarda arar ve aramayı review'a kaydeder (başlatan: terminal).",
        "en": "Search the sources and record the search in a review (started from: terminal).",
    },
    "help.search.query": {
        "tr": 'Sorgu, örn. "code review" AND (LLM OR "large language model")',
        "en": 'The query, e.g. "code review" AND (LLM OR "large language model")',
    },
    "help.search.sources": {
        "tr": "Virgülle kaynaklar: openalex (oa), semantic_scholar (s2), arxiv, crossref (cr), "
        "pubmed (pm). "
        "Varsayılan: hepsi.",
        "en": "Comma-separated sources: openalex (oa), semantic_scholar (s2), arxiv, "
        "crossref (cr), pubmed (pm). Default: all.",
    },
    "help.review": {
        "tr": "Review adı ya da kimliği (tek review varsa gerekmez).",
        "en": "Review title or id (not needed when there is only one).",
    },
    "help.search.year_from": {"tr": "Bu yıldan itibaren.", "en": "From this year."},
    "help.search.year_to": {"tr": "Bu yıla kadar.", "en": "Up to this year."},
    "help.search.limit": {
        "tr": "Kaynak başına en çok sonuç.",
        "en": "Most results per source.",
    },
    "help.import": {
        "tr": "Bir veritabanından dışa aktarılmış BibTeX/RIS dosyasını arama kaydı olarak "
        "içe alır.",
        "en": "Import a BibTeX/RIS file exported from a database, as a search run.",
    },
    "help.import.file": {"tr": ".bib veya .ris dosyası.", "en": "A .bib or .ris file."},
    "help.import.source": {
        "tr": 'Veritabanı adı, örn. "IEEE Xplore".',
        "en": 'Database name, e.g. "IEEE Xplore".',
    },
    "help.import.searched_at": {
        "tr": "Aramanın yapıldığı gün (YYYY-AA-GG; varsayılan: bugün).",
        "en": "Day the search was run (YYYY-MM-DD; default: today).",
    },
    "help.import.query": {
        "tr": "Veritabanında çalıştırılan sorgu.",
        "en": "The query as run at the database.",
    },
    "help.import.screening": {
        "tr": "Kayıtları review'un eleme kuyruğuna ekle (varsayılan: evet).",
        "en": "Put the records in the review's screening queue (default: yes).",
    },
    "help.import.library": {
        "tr": "Kayıtları kütüphaneye de ekle.",
        "en": "Also put the records in the library.",
    },
    "help.add": {
        "tr": "PDF'leri (ya da klasörlerdeki PDF'leri) Gelen kutusuna ekler; aynı dosya iki kez "
        "eklenmez.",
        "en": "Add PDFs (or the PDFs in folders) to the inbox; the same file is never added twice.",
    },
    "help.add.paths": {"tr": "PDF dosyaları ya da klasörler.", "en": "PDF files or folders."},
    "help.add.collection": {
        "tr": "Ayrıca bu koleksiyona koy (yoksa oluşturulur).",
        "en": "Also file them in this collection (made if missing).",
    },
    "help.export": {
        "tr": "Kaynakçayı BibTeX ya da RIS olarak yazar.",
        "en": "Write references as BibTeX or RIS.",
    },
    "help.export.format": {"tr": "bibtex veya ris.", "en": "bibtex or ris."},
    "help.export.review": {
        "tr": "Yalnızca bu review'daki makaleler.",
        "en": "Only the papers in this review.",
    },
    "help.export.collection": {
        "tr": "Yalnızca bu koleksiyondaki makaleler.",
        "en": "Only the papers in this collection.",
    },
    "help.export.output": {
        "tr": "Yazılacak dosya; verilmezse çıktıya yazılır.",
        "en": "File to write; standard output if not given.",
    },
    # --- output -------------------------------------------------------------------------
    "out.via_api": {
        "tr": "Açık TEz penceresi üzerinden çalışılıyor.",
        "en": "Working through the open TEz window.",
    },
    "out.direct": {
        "tr": "Kütüphane doğrudan açıldı: {path}",
        "en": "Library opened directly: {path}",
    },
    "out.state.searching": {"tr": "aranıyor", "en": "searching"},
    "out.state.rate_limited": {
        "tr": "hız sınırında, {seconds} sn bekleniyor",
        "en": "rate limited, waiting {seconds} s",
    },
    "out.state.done": {"tr": "{retrieved} kayıt", "en": "{retrieved} records"},
    "out.state.partial": {"tr": "{retrieved} kayıt (kısmi)", "en": "{retrieved} records (partial)"},
    "out.state.failed": {"tr": "hata: {error}", "en": "failed: {error}"},
    "out.search_done": {
        "tr": "{retrieved} kayıt · {duplicates} tekrar · {unique} benzersiz · arama {search_id}",
        "en": "{retrieved} records · {duplicates} duplicates · {unique} unique · search "
        "{search_id}",
    },
    "out.import_done": {
        "tr": "{total} girdiden {imported} tanesi içe alındı ({new} yeni makale); "
        "{to_review} kayıt review'a eklendi.",
        "en": "{imported} of {total} entries imported ({new} new papers); {to_review} records "
        "added to the review.",
    },
    "out.import_issue": {
        "tr": "  atlandı: satır {line} {key}: {code}",
        "en": "  skipped: line {line} {key}: {code}",
    },
    "out.added": {"tr": "eklendi", "en": "added"},
    "out.duplicate": {"tr": "zaten kütüphanede", "en": "already in the library"},
    "out.add_done": {
        "tr": "{added} eklendi · {duplicates} zaten vardı · {failed} eklenemedi",
        "en": "{added} added · {duplicates} already there · {failed} failed",
    },
    "out.add_later": {
        "tr": "PDF'ler TEz bir sonraki açılışında incelenecek (sayfa sayısı, metin katmanı).",
        "en": "The PDFs will be inspected (pages, text layer) the next time TEz opens.",
    },
    "out.filed": {"tr": "Koleksiyon: {name}", "en": "Collection: {name}"},
    "out.export_done": {
        "tr": "{count} kaynak yazıldı: {path}",
        "en": "{count} references written: {path}",
    },
    # --- errors (codes from the backend; anything else falls back to the code) -----------
    "error.library.not_found": {
        "tr": "Kütüphane bulunamadı: {path}",
        "en": "Library not found: {path}",
    },
    "error.library.locked": {
        "tr": "Kütüphane başka bir işlem tarafından kullanılıyor (pid {pid}).",
        "en": "The library is in use by another process (pid {pid}).",
    },
    "error.cli.library_busy": {
        "tr": "Kütüphane başka bir terminal komutu tarafından kullanılıyor (pid {pid}); "
        "bitmesini bekleyin.",
        "en": "Another terminal command is using the library (pid {pid}); wait for it to finish.",
    },
    "error.cli.api_unreachable": {
        "tr": "Açık TEz penceresine ulaşılamadı ({url}).",
        "en": "The open TEz window cannot be reached ({url}).",
    },
    "error.cli.no_review": {
        "tr": "Bu kütüphanede review yok; önce uygulamada bir review oluşturun.",
        "en": "This library has no review; create one in the app first.",
    },
    "error.cli.review_required": {
        "tr": "Birden çok review var; --review ile seçin: {reviews}",
        "en": "There are several reviews; choose one with --review: {reviews}",
    },
    "error.review.not_found": {
        "tr": "Review bulunamadı: {review}",
        "en": "Review not found: {review}",
    },
    "error.source.unknown": {
        "tr": "Bilinmeyen kaynak: {sources}",
        "en": "Unknown source: {sources}",
    },
    "error.import.unknown_format": {
        "tr": "{file_name} BibTeX ya da RIS dosyası değil.",
        "en": "{file_name} is neither a BibTeX nor a RIS file.",
    },
    "error.import.empty": {
        "tr": "{file_name} içinde içe aktarılabilecek kayıt yok.",
        "en": "{file_name} has no record that can be imported.",
    },
    "error.import.file_not_found": {
        "tr": "Dosya bulunamadı: {path}",
        "en": "File not found: {path}",
    },
    "error.import.entry_unparseable": {"tr": "okunamıyor", "en": "cannot be read"},
    "error.import.entry_no_title": {"tr": "başlığı yok", "en": "has no title"},
    "error.import.entry_duplicate_key": {
        "tr": "anahtarı dosyada tekrar ediyor",
        "en": "repeats a key used earlier",
    },
    "error.import.entry_truncated": {"tr": "yarıda kesilmiş", "en": "is cut short"},
    "error.import.stray_text": {
        "tr": "hiçbir kayda ait olmayan metin",
        "en": "text outside any record",
    },
    "error.pdf.not_a_pdf": {"tr": "PDF değil", "en": "not a PDF"},
    "error.pdf.file_not_found": {"tr": "dosya bulunamadı", "en": "file not found"},
    "error.pdf.too_large": {"tr": "çok büyük", "en": "too large"},
    "error.export.one_scope": {
        "tr": "--review ya da --collection'dan yalnızca biri verilebilir.",
        "en": "Give --review or --collection, not both.",
    },
    "error.collection.not_found": {
        "tr": "Koleksiyon bulunamadı.",
        "en": "Collection not found.",
    },
}


def _system_language() -> Language:
    if sys.platform == "win32":
        try:
            windll: Any = getattr(ctypes, "windll")  # noqa: B009 - absent on other systems
            langid = int(windll.kernel32.GetUserDefaultUILanguage())
            return "tr" if langid & 0x3FF == _WINDOWS_TURKISH else "en"
        except (AttributeError, OSError):
            pass
    for value in (os.environ.get("LC_ALL"), os.environ.get("LANG"), locale.getlocale()[0]):
        if value:
            return "tr" if value.lower().startswith("tr") else "en"
    return "en"


def detect_language(argv: Sequence[str]) -> Language:
    """`--lang tr|en` on the command line, then TEZ_LANG, then the system."""
    for index, argument in enumerate(argv):
        value = None
        if argument.startswith("--lang="):
            value = argument.partition("=")[2]
        elif argument == "--lang" and index + 1 < len(argv):
            value = argv[index + 1]
        if value in ("tr", "en"):
            return value
    env = os.environ.get("TEZ_LANG", "")
    if env in ("tr", "en"):
        return env
    return _system_language()


class Messages:
    def __init__(self, language: Language) -> None:
        self.language: Language = language

    def __call__(self, message: str, **params: Any) -> str:
        text = MESSAGES[message][self.language]
        return text.format(**params) if params else text

    def error(self, code: str, params: dict[str, Any]) -> str:
        template = MESSAGES.get(f"error.{code}")
        if template is None:
            details = ", ".join(f"{k}={v}" for k, v in params.items())
            return f"{code} ({details})" if details else code
        try:
            return template[self.language].format(**params)
        except (KeyError, IndexError):
            return template[self.language]


# Click and Typer write their own words in `--help` and in usage errors through `gettext`,
# with no Turkish catalogue. Their module-level `_` is swapped for one that knows these; a test
# checks the Turkish help, so a Typer update that moves them shows up there.
_CLICK_TR = {
    "Usage:": "Kullanım:",
    "Options": "Seçenekler",
    "Commands": "Komutlar",
    "Arguments": "Argümanlar",
    "Show this message and exit.": "Bu yardımı gösterir ve çıkar.",
    "default: {default}": "varsayılan: {default}",
    "required": "zorunlu",
    "Error: {message}": "Hata: {message}",
    "Try '{command} {option}' for help.": "Yardım için: '{command} {option}'",
    "Missing argument": "Eksik argüman",
    "Missing option": "Eksik seçenek",
    "Missing parameter": "Eksik parametre",
    "Missing command.": "Komut eksik.",
    "No such command {name!r}.": "Böyle bir komut yok: {name!r}.",
    "No such option {name!r}.": "Böyle bir seçenek yok: {name!r}.",
    "Invalid value for {param_hint}: {message}": "{param_hint} için geçersiz değer: {message}",
    "Invalid value: {message}": "Geçersiz değer: {message}",
    "Aborted!": "İptal edildi.",
}
# Typer carries its own copy of Click (typer._click).
_CLICK_MODULES = (
    "typer._click.core",
    "typer._click.decorators",
    "typer._click.exceptions",
    "typer._click.formatting",
    "typer._click.parser",
    "typer.core",
)


def translate_click(language: Language) -> None:
    """Make Click's and Typer's own help and error words Turkish when the CLI speaks Turkish."""
    if language != "tr":
        return
    import importlib

    for name in _CLICK_MODULES:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            # A Typer update moved it; the Turkish help test fails and says so.
            continue
        original = getattr(module, "_", None)
        if original is None or getattr(original, "__tez__", False):
            continue

        def translated(message: str, original: Any = original) -> str:
            return _CLICK_TR.get(message) or str(original(message))

        translated.__tez__ = True  # type: ignore[attr-defined]
        setattr(module, "_", translated)  # noqa: B010 - not a declared attribute

    # The help option's own text is written into the option, not looked up: set it there.
    try:
        command: Any = importlib.import_module("typer._click.core").Command
    except (ModuleNotFoundError, AttributeError):
        return
    original_get: Any = command.get_help_option
    if getattr(original_get, "__tez__", False):
        return

    def get_help_option(self: Any, ctx: Any) -> Any:
        option = original_get(self, ctx)
        if option is not None:
            option.help = _CLICK_TR["Show this message and exit."]
        return option

    get_help_option.__tez__ = True  # type: ignore[attr-defined]
    setattr(command, "get_help_option", get_help_option)  # noqa: B010
