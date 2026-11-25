"""Write the sample PDFs into out/: LaTeX (T1, OT1), Chromium (print.mjs), rotated and cropped
copies. Nothing is downloaded (MiKTeX's package installer is off)."""

import subprocess
from pathlib import Path

import pypdfium2 as pdfium
from texts import EN, TR

HERE = Path(__file__).parent
OUT = HERE.parent / "out"


def paragraphs(times: int) -> list[str]:
    texts: list[str] = []
    for round_no in range(times):
        for index in range(4):
            texts.append(f"({round_no + 1}.{index + 1}) {EN[index]}")
            if index < 3:
                texts.append(TR[index])
    return texts


def tex(body: str, enc: str, two: bool) -> str:
    font = r"\usepackage[T1]{fontenc}" if enc == "T1" else ""
    options = "10pt,twocolumn" if two else "11pt"
    lines = [
        rf"\documentclass[{options}]{{article}}",
        r"\usepackage[utf8]{inputenc}",
        font,
        r"\begin{document}",
        r"\section{Method and fieldwork}",
        r"A formula $E = mc^2 + \sum_{i=1}^{n} x_i$ sits inline.\footnote{A footnote about "
        r"efficient filing that is long enough to wrap over a couple of lines in the column.}",
        "",
        body,
        r"\end{document}",
    ]
    return "\n".join(lines)


def latex(name: str, enc: str, two: bool) -> None:
    body = "\n\n".join(p.replace("<", "$<$") for p in paragraphs(4))
    (OUT / f"{name}.tex").write_text(tex(body, enc, two), encoding="utf-8")
    command = [
        "pdflatex",
        "-disable-installer",
        "-interaction=batchmode",
        f"{name}.tex",
    ]
    done = subprocess.run(command, cwd=OUT, check=False)
    print(name, "exit", done.returncode, (OUT / f"{name}.pdf").exists())


def html(name: str, two: bool, lang: str) -> None:
    items = paragraphs(4) if lang == "en" else TR * 6
    columns = "column-count:2;column-gap:8mm" if two else ""
    style = (
        "body{font:10pt 'Cambria','Times New Roman',serif;text-align:justify;hyphens:auto;"
        + columns
        + "} p{margin:0 0 6pt}"
    )
    text = "".join(f"<p>{p.replace('<', '&lt;')}</p>" for p in items)
    (OUT / f"{name}.html").write_text(
        f"<!doctype html><html lang={lang}><meta charset=utf-8><style>{style}</style>{text}",
        encoding="utf-8",
    )


def derive(source: str) -> None:
    for angle in (90, 180, 270):
        doc = pdfium.PdfDocument(OUT / f"{source}.pdf")
        for page in doc:
            page.set_rotation(angle)
        doc.save(OUT / f"{source}-rot{angle}.pdf")
        doc.close()
    doc = pdfium.PdfDocument(OUT / f"{source}.pdf")
    for page in doc:
        left, bottom, right, top = page.get_mediabox()
        page.set_cropbox(left + 12, bottom + 14, right - 8, top - 10)
    doc.save(OUT / f"{source}-cropped.pdf")
    doc.close()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    latex("latex-t1-two", "T1", True)
    latex("latex-ot1-two", "OT1", True)
    latex("latex-t1-one", "T1", False)
    html("chromium-two", True, "en")
    html("chromium-tr", False, "tr")
    subprocess.run(["node", str(HERE / "print.mjs")], check=True)
    for source in ("latex-t1-two", "chromium-two"):
        if (OUT / f"{source}.pdf").exists():
            derive(source)


if __name__ == "__main__":
    main()
