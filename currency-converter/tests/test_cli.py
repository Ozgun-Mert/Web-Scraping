# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ozgun-Mert

"""Run currency_convert.py as a command, answering its downloads from the cached feeds."""

import runpy
import sys
from decimal import Decimal
from pathlib import Path

import pytest

import currency_convert as cc

SCRIPT = Path(__file__).resolve().parent.parent / "currency_convert.py"


@pytest.fixture
def run_cli(monkeypatch, capsys, cached_network):
    """Run the script with the given arguments; return (exit code, everything it printed)."""

    def run(*args):
        monkeypatch.setattr(sys, "argv", [SCRIPT.name, *args])
        code = 0
        try:
            runpy.run_path(str(SCRIPT), run_name="__main__")
        except SystemExit as e:
            code = e.code
        out, err = capsys.readouterr()
        return code, out + err

    return run


def expected(tcmb_rates, ecb_rates, amount, from_code, to_code):
    result = cc.select_converter(tcmb_rates, ecb_rates, Decimal(amount), from_code, to_code)
    return str(result.quantize(Decimal("0.01")))


def test_converts_and_prints_two_decimals(run_cli, tcmb_rates, ecb_rates):
    code, output = run_cli("100", "USD", "TRY")
    assert code == 0
    assert output.strip() == expected(tcmb_rates, ecb_rates, "100", "USD", "TRY")


def test_accepts_lowercase_codes_and_decimal_amounts(run_cli, tcmb_rates, ecb_rates):
    code, output = run_cli("2.5", "gbp", "jpy")
    assert code == 0
    assert output.strip() == expected(tcmb_rates, ecb_rates, "2.5", "GBP", "JPY")


def test_unknown_currency_prints_a_message(run_cli):
    _, output = run_cli("100", "USD", "XYZ")
    assert output.strip(), "nothing was printed"
    assert "Traceback" not in output


def test_invalid_amount_tells_the_user(run_cli):
    _, output = run_cli("abc", "USD", "TRY")
    assert "abc" in output, f"the user isn't told that 'abc' is not a number; output was {output!r}"


def test_missing_argument_is_an_error(run_cli):
    code, output = run_cli("100", "USD")
    assert code == 2
    assert "to_code" in output


def test_help_lists_the_arguments(run_cli):
    code, output = run_cli("--help")
    assert code == 0
    for name in ["amount", "from_code", "to_code"]:
        assert name in output
