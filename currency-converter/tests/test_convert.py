# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ozgun-Mert

"""select_converter: easy made-up rates for exact answers, plus checks on the live rates."""

from decimal import Decimal

import pytest

import currency_convert as cc

# TCMB style: lira per 1 unit. KWD exists only here.
TCMB = {
    "TRY": Decimal("1"),
    "USD": Decimal("40"),
    "EUR": Decimal("49"),
    "KWD": Decimal("130"),
    "JPY": Decimal("0.25"),
}

# ECB style: units per 1 euro. GBP and ISK exist only here.
ECB = {
    "EUR": Decimal("1"),
    "USD": Decimal("1.25"),
    "TRY": Decimal("50"),
    "GBP": Decimal("0.8"),
    "ISK": Decimal("150"),
}


def convert(amount, from_code, to_code):
    return cc.select_converter(TCMB, ECB, Decimal(amount), from_code, to_code)


@pytest.mark.parametrize(
    "amount, from_code, to_code, expected",
    [
        # with TRY, from TCMB
        ("100", "USD", "TRY", "4000"),
        ("4000", "TRY", "USD", "100"),
        ("100", "JPY", "TRY", "25"),
        ("130", "TRY", "KWD", "1"),
        # with EUR, from ECB
        ("100", "EUR", "USD", "125"),
        ("100", "USD", "EUR", "80"),
        ("100", "EUR", "GBP", "80"),
        # EUR and TRY are in both feeds; EUR pairs go to the ECB (50), not TCMB (49)
        ("100", "EUR", "TRY", "5000"),
        ("5000", "TRY", "EUR", "100"),
        # neither base currency, both in the ECB
        ("100", "USD", "GBP", "64"),
        # TRY with a currency only the ECB has
        ("100", "TRY", "ISK", "300"),
        ("300", "ISK", "TRY", "100"),
        # currencies only TCMB has
        ("100", "KWD", "USD", "325"),
        ("100", "KWD", "EUR", "265.3061224489795918367346939"),
        ("130", "EUR", "KWD", "49"),
    ],
)
def test_known_rates(amount, from_code, to_code, expected):
    assert convert(amount, from_code, to_code) == pytest.approx(Decimal(expected))


@pytest.mark.parametrize("code", ["TRY", "EUR", "USD", "KWD", "ISK"])
def test_same_currency_returns_same_amount(code):
    assert convert("100", code, code) == pytest.approx(Decimal("100"))


def test_result_is_decimal():
    assert isinstance(convert("100", "USD", "TRY"), Decimal)


@pytest.mark.parametrize(
    "from_code, to_code",
    [
        ("USD", "XYZ"),
        ("XYZ", "USD"),
        ("XYZ", "EUR"),
        ("TRY", "XYZ"),
        ("ISK", "KWD"),  # each exists in only one feed
    ],
)
def test_unknown_or_uncovered_pair_raises(from_code, to_code):
    with pytest.raises(ValueError):
        convert("100", from_code, to_code)


# --- live rates (downloaded once in conftest.py) ---

LIVE_PAIRS = [
    ("USD", "TRY"), ("TRY", "USD"), ("EUR", "TRY"), ("EUR", "USD"), ("USD", "EUR"),
    ("GBP", "JPY"), ("USD", "GBP"), ("KWD", "SAR"), ("KWD", "EUR"), ("EUR", "KWD"),
    ("TRY", "ISK"), ("ISK", "TRY"), ("JPY", "TRY"),
]


@pytest.mark.parametrize("from_code, to_code", LIVE_PAIRS)
def test_live_round_trip(tcmb_rates, ecb_rates, from_code, to_code):
    there = cc.select_converter(tcmb_rates, ecb_rates, Decimal("100"), from_code, to_code)
    back = cc.select_converter(tcmb_rates, ecb_rates, there, to_code, from_code)
    assert back == pytest.approx(Decimal("100"), rel=Decimal("1e-9"))


def test_live_usd_to_try_uses_tcmb_rate(tcmb_rates, ecb_rates):
    result = cc.select_converter(tcmb_rates, ecb_rates, Decimal("100"), "USD", "TRY")
    assert result == pytest.approx(100 * tcmb_rates["USD"])


def test_live_eur_to_usd_uses_ecb_rate(tcmb_rates, ecb_rates):
    result = cc.select_converter(tcmb_rates, ecb_rates, Decimal("100"), "EUR", "USD")
    assert result == pytest.approx(100 * ecb_rates["USD"])


def test_live_sources_agree_on_usd_to_try(tcmb_rates, ecb_rates):
    from_tcmb = cc.select_converter(tcmb_rates, ecb_rates, Decimal("100"), "USD", "TRY")
    via_ecb = 100 * ecb_rates["TRY"] / ecb_rates["USD"]
    assert from_tcmb == pytest.approx(via_ecb, rel=Decimal("0.02"))
