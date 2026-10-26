# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ozgun-Mert

"""parse_tcmb and parse_ecb: small hand-written XML for exact values, plus the live feeds."""

from datetime import date
from decimal import Decimal

import defusedxml.ElementTree as ET
import pytest

import currency_convert as cc

TCMB_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="23.10.2026" Date="10/23/2026" Bulten_No="2026/201">
  <Currency Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit><ForexBuying>40.5000</ForexBuying><BanknoteBuying>40.4000</BanknoteBuying>
  </Currency>
  <Currency Kod="JPY" CurrencyCode="JPY">
    <Unit>100</Unit><ForexBuying>25.0000</ForexBuying><BanknoteBuying>24.9000</BanknoteBuying>
  </Currency>
  <Currency Kod="RUB" CurrencyCode="RUB">
    <Unit>1</Unit><ForexBuying>0.5000</ForexBuying><BanknoteBuying></BanknoteBuying>
  </Currency>
  <Currency Kod="XDR" CurrencyCode="XDR">
    <Unit>1</Unit><ForexBuying></ForexBuying>
  </Currency>
  <Currency Kod="ABC" CurrencyCode="ABC">
    <Unit>1</Unit>
  </Currency>
</Tarih_Date>"""

ECB_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
                 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <Cube>
    <Cube time="2026-10-23">
      <Cube currency="USD" rate="1.25"/>
      <Cube currency="TRY" rate="50.5"/>
    </Cube>
  </Cube>
</gesmes:Envelope>"""


# --- TCMB, hand-written XML ---

def test_tcmb_reads_date():
    _, rate_date = cc.parse_tcmb(TCMB_SAMPLE)
    assert rate_date == date(2026, 10, 23)


def test_tcmb_reads_forex_buying_as_decimal():
    rates, _ = cc.parse_tcmb(TCMB_SAMPLE)
    assert rates["USD"] == Decimal("40.5")
    assert isinstance(rates["USD"], Decimal)


def test_tcmb_divides_by_unit():
    rates, _ = cc.parse_tcmb(TCMB_SAMPLE)
    assert rates["JPY"] == Decimal("0.25")  # 25 TRY per 100 yen


def test_tcmb_uses_forex_even_when_banknote_is_empty():
    rates, _ = cc.parse_tcmb(TCMB_SAMPLE)
    assert rates["RUB"] == Decimal("0.5")


@pytest.mark.parametrize("code", ["XDR", "ABC"])
def test_tcmb_skips_currency_without_forex_buying(code):
    rates, _ = cc.parse_tcmb(TCMB_SAMPLE)
    assert code not in rates


def test_tcmb_adds_try_as_one():
    rates, _ = cc.parse_tcmb(TCMB_SAMPLE)
    assert rates["TRY"] == Decimal("1")


# --- ECB, hand-written XML ---

def test_ecb_reads_rates_as_decimal():
    rates, _ = cc.parse_ecb(ECB_SAMPLE)
    assert rates["USD"] == Decimal("1.25")
    assert rates["TRY"] == Decimal("50.5")
    assert all(isinstance(r, Decimal) for r in rates.values())


def test_ecb_adds_eur_as_one():
    rates, _ = cc.parse_ecb(ECB_SAMPLE)
    assert rates["EUR"] == Decimal("1")


def test_ecb_reads_date():
    _, rate_date = cc.parse_ecb(ECB_SAMPLE)
    assert str(rate_date) == "2026-10-23"


def test_ecb_without_date_raises():
    no_date = ECB_SAMPLE.replace(b' time="2026-10-23"', b"")
    with pytest.raises(ValueError):
        cc.parse_ecb(no_date)


def test_broken_xml_raises():
    with pytest.raises(ET.ParseError):
        cc.parse_tcmb(b"<Tarih_Date><Currency></Tarih_Date>")


# --- live feeds: compare the parser with a direct read of the same XML ---

def test_live_tcmb_matches_raw_xml(tcmb_xml, tcmb_rates):
    root = ET.fromstring(tcmb_xml)
    expected = {}
    for currency in root.findall("Currency"):
        price = currency.findtext("ForexBuying")
        if price:
            expected[currency.get("Kod")] = Decimal(price) / Decimal(currency.findtext("Unit"))
    expected["TRY"] = Decimal("1")
    assert tcmb_rates == expected


def test_live_tcmb_has_main_currencies(tcmb_rates):
    for code in ["USD", "EUR", "GBP", "JPY", "CHF"]:
        assert code in tcmb_rates
    assert tcmb_rates["JPY"] < 1  # per 1 yen, not per 100


def test_live_tcmb_date_matches_feed(tcmb_xml, tcmb):
    _, rate_date = tcmb
    month, day, year = ET.fromstring(tcmb_xml).get("Date").split("/")
    assert rate_date == date(int(year), int(month), int(day))


def test_live_ecb_matches_raw_xml(ecb_xml, ecb_rates):
    cubes = ET.fromstring(ecb_xml).findall(".//{*}Cube[@currency]")
    expected = {c.get("currency"): Decimal(c.get("rate")) for c in cubes}
    expected["EUR"] = Decimal("1")
    assert ecb_rates == expected


def test_live_ecb_date_matches_feed(ecb_xml, ecb):
    _, rate_date = ecb
    assert str(rate_date) == ET.fromstring(ecb_xml).find(".//{*}Cube[@time]").get("time")


def test_live_feeds_agree_on_eur_try(tcmb_rates, ecb_rates):
    # Different times and buy vs. mid rates, but a parsing mistake would be far more than 2% off.
    assert tcmb_rates["EUR"] == pytest.approx(ecb_rates["TRY"], rel=Decimal("0.02"))
