# Currency converter

A command-line tool that converts an amount between currencies using the
official daily rates published by the Central Bank of the Republic of Turkey
(TCMB) and the European Central Bank (ECB).

## Setup

Run every command below from inside this folder (`currency-converter`).

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
venv's Python directly instead, e.g. `.venv\Scripts\python currency_convert.py 100 usd try`.

## Usage

```bash
python currency_convert.py 100 usd try
python currency_convert.py 2.5 GBP JPY
python currency_convert.py 100 kwd eur
```

```
> python currency_convert.py 100 usd try
4967.32
```

| Argument | Meaning |
| --- | --- |
| `amount` | The amount to convert, e.g. `100` or `2.5` |
| `from_code` | Three-letter code of the currency you have, e.g. `usd` (any case) |
| `to_code` | Three-letter code of the currency you want, e.g. `try` |

The result is rounded to two decimals. Wrong input is reported without a
traceback:

```
> python currency_convert.py abc usd try
usage: currency_convert.py [-h] amount from_code to_code
currency_convert.py: error: not a number: abc

> python currency_convert.py 100 usd xyz
Given currencies may not be in the list!
```

### Supported currencies

Whatever the two feeds publish that day. In October 2026 that was 39
currencies:

- **Both feeds:** EUR, TRY, USD, GBP, JPY, CHF, AUD, CAD, CNY, DKK, KRW, NOK, RON, SEK
- **ECB only:** BRL, CZK, HKD, HUF, IDR, ILS, INR, ISK, MXN, MYR, NZD, PHP, PLN, SGD, THB, ZAR
- **TCMB only:** AED, AZN, KWD, KZT, PKR, QAR, RUB, SAR, XDR

## How it works

1. `requests` downloads both XML feeds:
   - TCMB: `https://www.tcmb.gov.tr/kurlar/today.xml`
   - ECB: `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`
2. `defusedxml` parses them. It works like Python's own `xml.etree.ElementTree`
   but refuses malicious XML, which matters for files downloaded from the internet.
3. Each feed becomes a dictionary of rates, stored as `Decimal` so money is
   never rounded by floating-point errors:
   - **TCMB** gives lira per unit (`ForexBuying ÷ Unit`, because JPY is quoted
     per 100 yen). TRY is added with a rate of 1.
   - **ECB** gives units per one euro. EUR is added with a rate of 1.
4. One source is chosen for the pair, in this order:
   1. EUR is involved and the ECB has both currencies → ECB
   2. TRY is involved and TCMB has both currencies → TCMB
   3. The ECB has both currencies → ECB
   4. TCMB has both currencies → TCMB
   5. Otherwise the pair isn't covered, e.g. ISK (ECB only) → KWD (TCMB only)
5. The amount is converted with that source's formula:
   - TCMB: `amount × rate[from] ÷ rate[to]`
   - ECB: `amount × rate[to] ÷ rate[from]`

The two banks' rates differ slightly: they're published at different times, and
TCMB's forex buying rate isn't the ECB's mid-market reference rate. EUR ↔ TRY
uses the ECB rate (rule 1).

## Use in your own code

```python
from decimal import Decimal

from currency_convert import download, parse_ecb, parse_tcmb, select_converter

tcmb_rates, tcmb_date = parse_tcmb(download("https://www.tcmb.gov.tr/kurlar/today.xml"))
ecb_rates, ecb_date = parse_ecb(download("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"))

result = select_converter(tcmb_rates, ecb_rates, Decimal("100"), "USD", "TRY")
print(result.quantize(Decimal("0.01")))
```

Download and parse once, then reuse the rate dictionaries for as many
conversions as you need. `select_converter` raises `ValueError` for a pair
neither feed covers.

## Tests

With the venv active, install the test tools as well:

```bash
pip install -r requirements-dev.txt
```

Run all 66 tests:

```bash
python -m pytest
```

Each feed is downloaded **once per run** and shared by every test that needs
it (session-scoped fixtures in [tests/conftest.py](tests/conftest.py)). The
command-line tests run the script with its downloads answered from that same
copy. The last line of the output confirms it:

```
real downloads this run -> www.tcmb.gov.tr: 1, www.ecb.europa.eu: 1
```

The tests come in two kinds:

- **Offline (38, under a second):** hand-written XML and made-up rates with
  exact answers. They cover dividing by `Unit`, empty fields, the XML
  namespace, a missing date, broken XML, every source rule, same-currency
  conversions and unknown codes.
- **Live (28, about 10 seconds):** the real feeds. They check that the parsers
  match a direct read of the same XML, that the two banks agree within 2%,
  round trips (100 → there → back = 100) on 13 pairs, and the command line.
  Without internet they're skipped, not failed.

Run only the offline tests:

```bash
python -m pytest -m "not live"
```

## Limits

- Both banks publish on working days only: TCMB around 15:30 Turkish time,
  the ECB around 16:00 Central European time. Before that, and on weekends
  and holidays, you get the previous working day's rates.
- The rates are for information, not for payments or invoices. The ECB says
  its reference rates are for information only.
- Every run downloads both feeds again; nothing is cached yet.
- A pair needs one feed that has both currencies. Converting through EUR across
  the two feeds isn't supported.
- For an unknown currency the message doesn't name the wrong code, and the
  program still exits with code 0.

## License

Copyright (C) 2026 Ozgun-Mert

Licensed under the [GNU Affero General Public License v3.0](../LICENSE) or later.
You may use, change and share this code. If you share a changed version, or
run one as a service that other people use over a network, you must publish
your source code under the same license.

This project is not affiliated with or endorsed by the Central Bank of the
Republic of Turkey or the European Central Bank.
