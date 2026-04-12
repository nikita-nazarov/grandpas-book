#!/usr/bin/env python3
"""Transcribe handwritten Russian text from a PDF using the Gemini API."""

import argparse
import base64
import itertools
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

GEMINI_MODEL = "gemini-3.1-pro-preview"
PROMPT = (
    "Transcribe all handwritten Russian text from this document. "
    "Format the text into proper paragraphs and add correct punctuation. "
    "Output only the transcribed text with no commentary or labels."
)


def transcribe(pdf_path: Path, api_key: str) -> str:
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")

    payload = json.dumps({
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
                {"text": PROMPT},
            ]
        }]
    }).encode("utf-8")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP {e.code}: {body}") from None

    return result["candidates"][0]["content"]["parts"][0]["text"]


def process_file(pdf_path: Path, out_path: Path, api_key: str) -> None:
    text = transcribe(pdf_path, api_key)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


class Spinner:
    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._label = ""

    def start(self, label: str) -> None:
        self._label = label
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self) -> None:
        for frame in itertools.cycle(self._frames):
            if self._stop_event.is_set():
                break
            print(f"\r{frame} {self._label}", end="", flush=True)
            time.sleep(0.08)

    def stop(self, result_line: str) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        print(f"\r{result_line}")  # overwrite spinner line


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe handwritten Russian PDFs using Gemini."
    )
    parser.add_argument("input", help="PDF file or directory of PDFs")
    parser.add_argument(
        "-d", "--dest",
        help="Output file or directory (default: alongside input)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)

    # ── Single file ──────────────────────────────────────────────────────────
    if input_path.is_file():
        if args.dest:
            dest = Path(args.dest)
            # Treat as file if it has a suffix, otherwise as directory
            out_path = dest if dest.suffix else dest / (input_path.stem + ".txt")
        else:
            out_path = None  # print to stdout

        spinner = Spinner() if out_path else None
        if spinner:
            spinner.start(input_path.name)

        text = transcribe(input_path, api_key)

        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
            spinner.stop(f"✓ {input_path.name}")
        else:
            print(text)

    # ── Directory ────────────────────────────────────────────────────────────
    elif input_path.is_dir():
        pdfs = sorted(input_path.glob("*.pdf"))
        if not pdfs:
            print(f"No PDF files found in {input_path}", file=sys.stderr)
            sys.exit(1)

        out_dir = Path(args.dest) if args.dest else input_path
        out_dir.mkdir(parents=True, exist_ok=True)

        total = len(pdfs)
        errors = []
        spinner = Spinner()

        for i, pdf in enumerate(pdfs):
            spinner.start(f"{pdf.name}  ({i + 1}/{total})")
            try:
                process_file(pdf, out_dir / (pdf.stem + ".txt"), api_key)
                spinner.stop(f"✓ {pdf.name}  ({i + 1}/{total})")
            except Exception as e:
                spinner.stop(f"✗ {pdf.name}: {e}")
                errors.append((pdf.name, e))

        if errors:
            print("\nErrors:", file=sys.stderr)
            for name, err in errors:
                print(f"  {name}: {err}", file=sys.stderr)

    else:
        print(f"Error: {input_path} is not a valid file or directory", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
