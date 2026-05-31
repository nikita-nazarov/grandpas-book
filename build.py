#!/usr/bin/env python3
"""Build a static HTML book from Текст/все.txt using Tufte CSS.

Usage:
    python build.py
Then open _site/index.html in a browser.
"""

import re
import shutil
import urllib.request
from html import escape
from pathlib import Path

SOURCE = Path("Текст/все.txt")
OUT = Path("docs")

TUFTE_BASE = "https://raw.githubusercontent.com/edwardtufte/tufte-css/master/"
FONT_FILES = [
    "et-book/et-book-roman-line-figures/et-book-roman-line-figures.woff",
    "et-book/et-book-display-italic-old-style-figures/et-book-display-italic-old-style-figures.woff",
    "et-book/et-book-bold-line-figures/et-book-bold-line-figures.woff",
    "et-book/et-book-roman-old-style-figures/et-book-roman-old-style-figures.woff",
    "et-book/et-book-semi-bold-old-style-figures/et-book-semi-bold-old-style-figures.woff",
]

EXTRA_CSS = """
  /* navigation bar */
  .chapnav {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 1px solid #ddd;
    padding-bottom: 0.4rem;
    margin-bottom: 3rem;
    font-size: 0.85rem;
    color: #999;
  }
  .chapnav a { color: #555; text-decoration: none; }
  .chapnav a:hover { color: #111; }
  .chapnav .toc-link { letter-spacing: 0.05em; }

  /* bottom prev/next */
  .page-turn {
    display: flex;
    justify-content: space-between;
    margin-top: 4rem;
    padding-top: 1rem;
    border-top: 1px solid #ddd;
    font-size: 0.9rem;
  }
  .page-turn a { color: #555; text-decoration: none; }
  .page-turn a:hover { color: #111; }
  .page-turn .disabled { color: #ccc; pointer-events: none; }

  /* table of contents */
  .toc-page h1 { margin-bottom: 0.3rem; }
  .toc-page .subtitle { margin-top: 0; color: #888; font-style: italic; }
  .toc-list { padding-left: 1.4rem; margin-top: 3rem; line-height: 2; }
  .toc-list li { font-size: 1.1rem; }
  .toc-list a { color: #111; text-decoration: none; border-bottom: 1px solid #ccc; }
  .toc-list a:hover { border-bottom-color: #111; }
"""


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        print(f"  скачиваю {dest}")
        urllib.request.urlretrieve(url, dest)


def paragraphs_to_html(body: str) -> str:
    paras = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
    return "\n".join(f"    <p>{escape(p)}</p>" for p in paras)


def render_page(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <link rel="stylesheet" href="tufte.css">
  <style>{EXTRA_CSS}  </style>
</head>
<body>
<article>
{body_html}
</article>
</body>
</html>
"""


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

    print("Загружаю Tufte CSS и шрифты...")
    download(TUFTE_BASE + "tufte.css", OUT / "tufte.css")
    for f in FONT_FILES:
        download(TUFTE_BASE + f, OUT / f)

    total = len(chapters)

    # --- contents.html — book-style TOC ---
    items = "\n".join(
        f'      <li><a href="{"index" if n == 1 else f"chapter-{n}"}.html">Древо {escape(t)}</a></li>'
        for n, (t, _) in enumerate(chapters, 1)
    )
    toc_html = f"""\
  <div class="toc-page">
    <h1>Воспоминания</h1>
    <p class="subtitle">Книга памяти</p>
    <ol class="toc-list">
{items}
    </ol>
  </div>"""
    (OUT / "contents.html").write_text(
        render_page("Содержание — Воспоминания", toc_html), encoding="utf-8"
    )

    # --- chapters; index.html = chapter 1 ---
    for n, (title, body) in enumerate(chapters, 1):
        prev_link = f'<a href="chapter-{n-1}.html">← Древо {escape(chapters[n-2][0])}</a>' if n > 1 else '<span class="disabled">←</span>'
        next_link = f'<a href="chapter-{n+1}.html">Древо {escape(chapters[n][0])} →</a>' if n < total else '<span class="disabled">→</span>'

        chapter_html = f"""\
  <div class="chapnav">
    <a class="toc-link" href="contents.html">Содержание</a>
    <span></span>
  </div>
  <h1>Древо {escape(title)}</h1>
  <section>
{paragraphs_to_html(body)}
  </section>
  <div class="page-turn">
    {prev_link}
    {next_link}
  </div>"""

        filename = "index.html" if n == 1 else f"chapter-{n}.html"
        (OUT / filename).write_text(
            render_page(f"Древо {title} — Воспоминания", chapter_html),
            encoding="utf-8",
        )
        print(f"  {filename}  (Древо {title})")

    print(f"\nГотово: {total} глав → {OUT}/")
    print(f"Открыть: open {OUT}/index.html")


if __name__ == "__main__":
    main()
