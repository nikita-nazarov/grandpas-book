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
REQUEST_STAGGER_SECONDS = 1.0
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


class Spinner:
    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._label = ""
        self._lock = threading.Lock()

    def set_label(self, label: str) -> None:
        with self._lock:
            self._label = label

    def start(self, label: str) -> None:
        self.set_label(label)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self) -> None:
        for frame in itertools.cycle(self._frames):
            if self._stop_event.is_set():
                break
            with self._lock:
                label = self._label
            print(f"\r{frame} {label}", end="", flush=True)
            time.sleep(0.08)

    def stop(self, result_line: str) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        print(f"\r{result_line}")


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
        done_count = 0
        results: dict[Path, Exception | None] = {}
        lock = threading.Lock()
        spinner = Spinner()
        spinner.start(f"0/{total} done")

        def worker(i: int, pdf: Path) -> None:
            nonlocal done_count
            time.sleep(i * REQUEST_STAGGER_SECONDS)
            error = None
            try:
                text = transcribe(pdf, api_key)
                out_path = out_dir / (pdf.stem + ".txt")
                out_path.write_text(text, encoding="utf-8")
            except Exception as e:
                error = e
            with lock:
                done_count += 1
                results[pdf] = error
                spinner.set_label(f"{done_count}/{total} done")

        threads = [
            threading.Thread(target=worker, args=(i, pdf), daemon=True)
            for i, pdf in enumerate(pdfs)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        spinner.stop(f"✓ {total}/{total} done")

        for pdf in pdfs:
            err = results.get(pdf)
            if err:
                print(f"  ✗ {pdf.name}: {err}", file=sys.stderr)

    else:
        print(f"Error: {input_path} is not a valid file or directory", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
