# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Ozgun-Mert

"""Shared fixtures: each feed is downloaded once per test run and reused by every test."""

import pytest
import requests

import currency_convert as cc

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

# How many real downloads happened, shown in the summary at the end of the run.
download_count = {TCMB_URL: 0, ECB_URL: 0}


def fetch_once(url):
    try:
        data = cc.download(url)
    except requests.exceptions.RequestException as e:
        pytest.skip(f"could not download {url}: {e}")
    download_count[url] += 1
    return data


# scope="session" makes pytest call each fixture once and hand the same value to every test.
@pytest.fixture(scope="session")
def tcmb_xml():
    return fetch_once(TCMB_URL)


@pytest.fixture(scope="session")
def ecb_xml():
    return fetch_once(ECB_URL)


@pytest.fixture(scope="session")
def tcmb(tcmb_xml):
    """(rates, date) parsed from the live TCMB feed."""
    return cc.parse_tcmb(tcmb_xml)


@pytest.fixture(scope="session")
def ecb(ecb_xml):
    """(rates, date) parsed from the live ECB feed."""
    return cc.parse_ecb(ecb_xml)


@pytest.fixture(scope="session")
def tcmb_rates(tcmb):
    return tcmb[0]


@pytest.fixture(scope="session")
def ecb_rates(ecb):
    return ecb[0]


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


@pytest.fixture
def cached_network(monkeypatch, tcmb_xml, ecb_xml):
    """Make requests.get answer from the already-downloaded feeds instead of the internet."""
    feeds = {TCMB_URL: tcmb_xml, ECB_URL: ecb_xml}

    def fake_get(url, **kwargs):
        assert url in feeds, f"unexpected download: {url}"
        return FakeResponse(feeds[url])

    monkeypatch.setattr(requests, "get", fake_get)


LIVE_FIXTURES = {"tcmb_xml", "ecb_xml"}


def pytest_collection_modifyitems(items):
    """Mark every test that needs a real download as `live`, so `-m "not live"` runs offline."""
    for item in items:
        if LIVE_FIXTURES & set(item.fixturenames):
            item.add_marker(pytest.mark.live)


def pytest_terminal_summary(terminalreporter):
    counts = ", ".join(f"{url.split('/')[2]}: {n}" for url, n in download_count.items())
    terminalreporter.write_line(f"real downloads this run -> {counts}")
