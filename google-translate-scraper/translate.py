# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ozgun-Mert
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed WITHOUT ANY WARRANTY; see the
# LICENSE file for details.

"""Translate text by scraping Google Translate.

The text and the languages go into the URL, and the translation is read from
the page Google sends back. Two sources are supported:

  html  scrape https://translate.google.com/m (the lightweight mobile page)
  api   read https://translate.googleapis.com/translate_a/single, the JSON
        endpoint Google's own browser extension uses

By default ("auto") the HTML page is tried first, and the JSON endpoint is
used when Google blocks the page or the page has no translation on it.

Usage:
    python translate.py "Hello, how are you?" --to tr
    python translate.py "Guten Morgen" --from de --to en
    python translate.py "Good night" --to turkish
    echo "Bonjour" | python translate.py --to en
    python translate.py --file notes.txt --to es
    python translate.py "Hello" --to tr --method html --show-url
"""

import argparse
import difflib
import sys

import requests
from bs4 import BeautifulSoup

from languages import ALIASES, LANGUAGES

HTML_URL = "https://translate.google.com/m"
API_URL = "https://translate.googleapis.com/translate_a/single"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
# Long texts make the URL too long for Google, so they are sent in pieces.
MAX_CHUNK_CHARS = 1500
# Where a piece may end, best first: after a sentence, then at a space.
SENTENCE_ENDS = (". ", "! ", "? ", "; ", "。", "！", "？", "؟ ")

# Lower-cased code, alias or English name -> Google's code. Names go in first
# so that a code always wins (the language "Ga" is "gaa"; the code "ga" is Irish).
_LOOKUP = {name.lower(): code for code, name in LANGUAGES.items()}
_LOOKUP.update({code.lower(): code for code in LANGUAGES})
_LOOKUP.update(ALIASES)


class TranslationError(Exception):
    pass


class BlockedError(TranslationError):
    """Google answered with a CAPTCHA page or a rate limit instead of a result."""


def resolve_language(value, allow_auto=False):
    """Turn a code, alias or English name ('TR', 'he', 'Turkish') into Google's code.

    Google silently returns the text untranslated for codes it doesn't know,
    so unknown languages are rejected here instead.
    """
    key = value.strip().lower()
    if allow_auto and key == "auto":
        return "auto"
    if key in _LOOKUP:
        return _LOOKUP[key]

    message = f"Unknown language '{value}'."
    matches = difflib.get_close_matches(key, _LOOKUP, n=3, cutoff=0.6)
    suggestions = dict.fromkeys(_LOOKUP[m] for m in matches)
    if suggestions:
        message += " Did you mean: " + ", ".join(
            f"{LANGUAGES[code]} ({code})" for code in suggestions
        ) + "?"
    raise TranslationError(message)


def build_url(text, target, source="auto", method="html"):
    """Return the URL that holds the text and the languages."""
    if method == "api":
        params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}
        base = API_URL
    else:
        params = {"sl": source, "tl": target, "q": text}
        base = HTML_URL
    return requests.Request("GET", base, params=params).prepare().url


def _cut_point(line, limit):
    """Where to cut a line longer than `limit`: after a sentence if possible."""
    window = line[:limit]
    sentence_end = max(
        (window.rfind(end) + len(end.rstrip()) for end in SENTENCE_ENDS
         if window.rfind(end) > 0),
        default=0,
    )
    if sentence_end > limit // 2:
        return sentence_end
    space = window.rfind(" ")
    return space if space > 0 else limit


def split_text(text, limit=MAX_CHUNK_CHARS):
    """Split text into pieces of at most `limit` characters.

    Pieces end at line breaks where possible, otherwise after a sentence, at a
    space, or (for one very long word) anywhere. Joined back together, the
    pieces are exactly the original text.
    """
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            cut = _cut_point(line, limit)
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:cut])
            line = line[cut:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return chunks


def fetch(session, url):
    try:
        response = session.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as exc:
        raise TranslationError(f"Could not reach Google: {exc}") from exc

    if response.status_code == 429 or "/sorry/" in response.url:
        raise BlockedError(
            "Google blocked the request with a CAPTCHA / rate limit (HTTP 429)."
        )
    if response.status_code != 200:
        raise TranslationError(f"Google returned HTTP {response.status_code}.")
    return response


def translate_chunk_html(session, text, target, source):
    response = fetch(session, build_url(text, target, source, "html"))
    result = BeautifulSoup(response.text, "html.parser").find(
        "div", class_="result-container"
    )
    if result is None:
        raise TranslationError(
            "Translation not found on the page. Google may have changed its HTML."
        )
    return result.get_text()


def translate_chunk_api(session, text, target, source):
    response = fetch(session, build_url(text, target, source, "api"))
    try:
        # data[0] is a list of [translated sentence, original sentence, ...]
        sentences = response.json()[0]
        translation = "".join(sentence[0] for sentence in sentences if sentence[0])
    except (ValueError, LookupError, TypeError) as exc:
        raise TranslationError("Unexpected response format from Google.") from exc
    if not translation.strip():
        raise TranslationError("Google returned an empty translation.")
    return translation


def translate(text, target, source="auto", method="auto"):
    """Translate `text` into the `target` language (e.g. 'tr', 'en', 'German').

    Returns (translation, method_used), where method_used is "html" or "api".
    Line breaks and blank lines in the text are kept.
    """
    target = resolve_language(target)
    source = resolve_language(source, allow_auto=True)
    text = text.strip()
    if not text:
        raise TranslationError("Nothing to translate.")

    current = "api" if method == "api" else "html"
    pieces = []
    with requests.Session() as session:
        for chunk in split_text(text, MAX_CHUNK_CHARS):
            core = chunk.strip()
            if not core:
                pieces.append(chunk)
                continue
            # Keep the spaces / line breaks around each piece, so the pieces
            # join back into the same paragraphs and sentences.
            lead = chunk[: len(chunk) - len(chunk.lstrip())]
            trail = chunk[len(chunk.rstrip()):]
            translation = None
            if current == "html":
                try:
                    translation = translate_chunk_html(session, core, target, source)
                except TranslationError:
                    if method == "html":
                        raise
                    current = "api"
            if translation is None:
                translation = translate_chunk_api(session, core, target, source)
            pieces.append(lead + translation.strip() + trail)
    return "".join(pieces).strip(), current


def main():
    parser = argparse.ArgumentParser(
        description="Translate text by scraping Google Translate."
    )
    parser.add_argument("text", nargs="?", help="text to translate (or pipe it in)")
    parser.add_argument(
        "-t", "--to", required=True,
        help="target language: code or English name, e.g. tr or turkish",
    )
    parser.add_argument(
        "-f", "--from", dest="source", default="auto",
        help="source language (default: auto-detect)",
    )
    parser.add_argument("--file", help="read the text from this file (UTF-8)")
    parser.add_argument(
        "-m", "--method", choices=["auto", "html", "api"], default="auto",
        help="html = scrape the web page, api = JSON endpoint, "
             "auto = html with api fallback (default)",
    )
    parser.add_argument(
        "--show-url", action="store_true", help="also print the URL that was scraped"
    )
    args = parser.parse_args()

    # Windows consoles default to a code page that can't handle many languages.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    try:
        if args.file:
            try:
                # utf-8-sig drops the BOM that Notepad and PowerShell add
                with open(args.file, encoding="utf-8-sig") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError) as exc:
                raise TranslationError(f"Could not read '{args.file}': {exc}") from exc
        elif args.text is not None:
            text = args.text
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            parser.error("give the text as an argument, with --file, or through a pipe")

        target = resolve_language(args.to)
        source = resolve_language(args.source, allow_auto=True)
        translation, used = translate(text, target, source, args.method)
    except TranslationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.method == "auto" and used == "api":
        print("(HTML page was blocked or unreadable; used the JSON endpoint)",
              file=sys.stderr)
    if args.show_url:
        print(f"URL: {build_url(text.strip(), target, source, used)}\n")
    print(translation)


if __name__ == "__main__":
    main()
