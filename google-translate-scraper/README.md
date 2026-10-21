# Google Translate scraper

A command-line tool that translates text by putting the text and the target
language into a Google Translate URL and reading the translation from the
response.

## Setup

Run every command below from inside this folder (`google-translate-scraper`).

Create a virtual environment so the packages stay inside this project:

```bash
python -m venv .venv
```

Activate it (once per terminal):

| Terminal | Command |
| --- | --- |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |
| Git Bash | `source .venv/Scripts/activate` |
| macOS / Linux | `source .venv/bin/activate` |

Then install the requirements:

```bash
pip install -r requirements.txt
```

If PowerShell says running scripts is disabled, skip activating and call the
venv's Python directly instead, e.g. `.venv\Scripts\python translate.py "Hello" --to tr`.

## Usage

```bash
python translate.py "Hello, how are you?" --to tr
python translate.py "Guten Morgen" --from de --to en
echo "Bonjour" | python translate.py --to en
python translate.py --file notes.txt --to es
python translate.py "Hello" --to tr --show-url
python translate.py "Good night" --to turkish
```

| Option | Meaning |
| --- | --- |
| `-t, --to` | Target language (required): a code like `tr`, `zh-CN`, `he`, or an English name like `turkish` |
| `-f, --from` | Source language, default `auto` (Google detects it) |
| `--file` | Read the text from a UTF-8 file instead of the command line |
| `-m, --method` | `auto` (default), `html` or `api`; see below |
| `--show-url` | Also print the URL that was requested |

All 249 supported languages are listed in
[languages.py](languages.py). Codes
and names are checked before anything is sent, because Google silently
returns the text untranslated when it doesn't know a code:

```
> python translate.py "Hello" --to tur
Error: Unknown language 'tur'. Did you mean: Urdu (ur), Turkish (tr), Tumbuka (tum)?
```

## How it works

1. The text and languages are put into a URL, e.g.
   `https://translate.google.com/m?sl=auto&tl=tr&q=Hello`
2. `requests` downloads that page.
3. BeautifulSoup finds `<div class="result-container">` and reads the translation.

Long texts are split into pieces of at most 1500 characters, so the URL never
gets too long. Pieces end at a line break or the end of a sentence where
possible (also `。！？` for Chinese/Japanese), and are joined back with the
original line breaks and paragraphs.

### Methods

- **html** scrapes the lightweight mobile page `translate.google.com/m`, as above.
- **api** reads `translate.googleapis.com/translate_a/single?client=gtx`, the
  JSON endpoint Google's own browser extension uses. It's lighter and is
  blocked much less often.
- **auto** tries `html` first and switches to `api` when Google answers with
  its CAPTCHA page (`google.com/sorry`), HTTP 429, or a page with no
  translation on it.

## Use in your own code

```python
from translate import translate

text, method_used = translate("Hello world", target="tr")
print(text)
```

## Tests

With the venv active, install the test tools as well:

```bash
pip install -r requirements-dev.txt
```

Offline tests (about 260, under a second) replace Google with a fake server
and check exact behavior: language codes, URL encoding, splitting long text,
broken or blocked responses, the html → api fallback and the command line:

```bash
python -m pytest
```

Live tests send about 25 real requests to Google with hard cases: false
friends (German *Gift* = poison), very long Turkish and German words,
auto-detected languages, Japanese, Arabic, Greek, Chinese, Hebrew, emoji,
numbers, `& # % +` in the text, paragraphs, a 3600-character text and a
1400-character Japanese text:

```bash
python -m pytest -m live
```

## Limits

- Google's terms don't allow automated scraping. Use this for personal or
  learning projects. For anything serious, use the official Cloud Translation
  API (500k characters/month free) or DeepL's free API.
- Google often blocks scripted requests to the HTML page with a CAPTCHA, even
  the first one. When it does, `auto` uses the JSON endpoint instead.
- Neither endpoint is official, so either one can change or stop working
  without warning.

## License

Copyright (C) 2026 Ozgun-Mert

Licensed under the [GNU Affero General Public License v3.0](../LICENSE) or later.
You may use, change and share this code. If you share a changed version, or
run one as a service that other people use over a network, you must publish
your source code under the same license.

This project is not affiliated with or endorsed by Google. "Google Translate"
is a trademark of Google LLC.
