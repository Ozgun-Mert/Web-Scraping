# Web Scraping

A collection of small web scraping tools written in Python. Each tool lives in
its own folder, with its own dependencies, tests and README.

## Projects

| Project | What it does | Status |
| --- | --- | --- |
| [google-translate-scraper](google-translate-scraper/) | Translates text from the command line by scraping Google Translate, with a fallback to Google's JSON endpoint. Supports 249 languages. | Working, tested |

## Repository layout

```
Web Scraping/
├── .gitignore                  rules for every project
├── LICENSE                     AGPL-3.0, covers every project
├── README.md                   this file
└── google-translate-scraper/
    ├── README.md               setup, usage and how it works
    ├── translate.py            the tool
    ├── languages.py            supported languages
    ├── requirements.txt        packages the tool needs
    ├── requirements-dev.txt    packages for running the tests
    ├── pytest.ini
    └── tests/
```

## Getting started

Tested with Python 3.14.

Each project has its own virtual environment, so their packages never mix.
To set one up, go into its folder:

```bash
cd google-translate-scraper
```

Create the virtual environment:

```bash
python -m venv .venv
```

Activate it. This is the Windows PowerShell command; the project's README
lists the ones for other terminals:

```bash
.venv\Scripts\Activate.ps1
```

Install the packages:

```bash
pip install -r requirements.txt
```

Then follow that project's README for usage and tests.

## Adding a new project

1. Create a folder with a short, lowercase, hyphenated name, e.g. `price-tracker`.
2. Give it its own `requirements.txt` and `.venv` (the venv is ignored by git).
3. Add a `README.md` with setup, usage and limits.
4. Put tests in a `tests/` folder. Tests that hit real websites should be
   optional (see `google-translate-scraper/pytest.ini` for the `live` marker).
5. Start each source file with the license header:
   ```python
   # SPDX-License-Identifier: AGPL-3.0-or-later
   # Copyright (C) 2026 Ozgun-Mert
   ```
6. Add a row to the **Projects** table above.

Keep API keys, tokens and cookies in a `.env` file. It is ignored by git;
commit a `.env.example` with empty values instead.

## Scraping responsibly

- Check a site's terms of service and `robots.txt` before scraping it.
- Prefer an official API when one exists.
- Keep request rates low and add pauses between requests.
- Don't bypass CAPTCHAs, logins or other access controls.
- Don't collect personal data.

These tools are for personal and learning use.

## License

Copyright (C) 2026 Ozgun-Mert

Licensed under the [GNU Affero General Public License v3.0](LICENSE) or later.
You may use, change and share this code. If you share a changed version, or
run one as a service that other people use over a network, you must publish
your source code under the same license.

This repository is not affiliated with or endorsed by any of the websites it
scrapes. "Google Translate" is a trademark of Google LLC.
