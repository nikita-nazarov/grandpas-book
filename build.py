#!/usr/bin/env python3
"""Build a static HTML book from Текст/все.txt using Tufte CSS.

Usage:
    python3 build.py
Then open docs/index.html in a browser.
"""

import re
import shutil
import urllib.request
from html import escape
from pathlib import Path
from string import Template

SOURCE = Path("Текст/все.txt")
OUT = Path("docs")
TEMPLATES = Path("templates")

TUFTE_BASE = "https://raw.githubusercontent.com/edwardtufte/tufte-css/master/"
FONT_FILES = [
    "et-book/et-book-roman-line-figures/et-book-roman-line-figures.woff",
    "et-book/et-book-display-italic-old-style-figures/et-book-display-italic-old-style-figures.woff",
    "et-book/et-book-bold-line-figures/et-book-bold-line-figures.woff",
    "et-book/et-book-roman-old-style-figures/et-book-roman-old-style-figures.woff",
    "et-book/et-book-semi-bold-old-style-figures/et-book-semi-bold-old-style-figures.woff",
]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        print(f"  скачиваю {dest}")
        urllib.request.urlretrieve(url, dest)


def paragraphs_to_html(body: str) -> str:
    paras = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
    return "\n    ".join(f"<p>{escape(p)}</p>" for p in paras)


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    parts = re.split(r"(?m)^(ДРЕВО .+)$", text)
    chapters: list[tuple[str, str]] = []
    i = 1
    while i < len(parts):
        title = parts[i].strip().removeprefix("ДРЕВО").strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        chapters.append((title, body))
        i += 2

    if not chapters:
        print("Главы не найдены — убедитесь что файл содержит строки вида «ДРЕВО N»")
        return

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir()

    # load templates
    chapter_tmpl = Template((TEMPLATES / "chapter.html").read_text(encoding="utf-8"))
    contents_tmpl = Template((TEMPLATES / "contents.html").read_text(encoding="utf-8"))

    print("Загружаю Tufte CSS и шрифты...")
    download(TUFTE_BASE + "tufte.css", OUT / "tufte.css")
    for f in FONT_FILES:
        download(TUFTE_BASE + f, OUT / f)

    # .nojekyll — отключает Jekyll на GitHub Pages
    (OUT / ".nojekyll").touch()

    total = len(chapters)

    # contents.html
    items = "\n    ".join(
        f'<li><a href="{"index" if n == 1 else f"chapter-{n}"}.html">Древо {escape(t)}</a></li>'
        for n, (t, _) in enumerate(chapters, 1)
    )
    (OUT / "contents.html").write_text(
        contents_tmpl.substitute(items=items), encoding="utf-8"
    )

    # chapter pages; chapter 1 → index.html
    for n, (title, body) in enumerate(chapters, 1):
        prev = (
            f'<a href="{"index" if n == 2 else f"chapter-{n-1}"}.html">← Древо {escape(chapters[n-2][0])}</a>'
            if n > 1 else '<span class="disabled">←</span>'
        )
        nxt = (
            f'<a href="chapter-{n+1}.html">Древо {escape(chapters[n][0])} →</a>'
            if n < total else '<span class="disabled">→</span>'
        )
        chapter_nav_parts = []
        for i, (t, _) in enumerate(chapters, 1):
            href = "index.html" if i == 1 else f"chapter-{i}.html"
            if i == n:
                chapter_nav_parts.append(f'<span class="chapnav-active">Древо {escape(t)}</span>')
            else:
                chapter_nav_parts.append(f'<a href="{href}">Древо {escape(t)}</a>')
        chapter_nav = "\n      ".join(chapter_nav_parts)
        html = chapter_tmpl.substitute(
            title=escape(f"Древо {title}"),
            heading=f"Древо {escape(title)}",
            body=paragraphs_to_html(body),
            nav_prev=prev,
            nav_next=nxt,
            chapter_nav=chapter_nav,
        )
        filename = "index.html" if n == 1 else f"chapter-{n}.html"
        (OUT / filename).write_text(html, encoding="utf-8")
        print(f"  {filename}  (Древо {title})")

    print(f"\nГотово: {total} глав → {OUT}/")
    print(f"Открыть: open {OUT}/index.html")


if __name__ == "__main__":
    main()
