"""A fake Google Translate, so unit tests run offline and can check exact output."""

import html
import json
from urllib.parse import parse_qs, urlparse

import pytest

import translate as tr


class FakeResponse:
    def __init__(self, status_code=200, text="", url="https://translate.google.com/m"):
        self.status_code = status_code
        self.text = text
        self.url = url

    def json(self):
        return json.loads(self.text)


def query(url):
    """Return the query parameters of `url` as {name: value}."""
    return {k: v[0] for k, v in parse_qs(urlparse(url).query, keep_blank_values=True).items()}


def is_api(url):
    return url.startswith(tr.API_URL)


def html_page(translation):
    return FakeResponse(
        text=f'<html><body><div class="result-container">{html.escape(translation)}'
             f"</div></body></html>"
    )


def api_json(*segments, url=tr.API_URL):
    """A JSON response like Google's: one [translated, original, ...] list per sentence."""
    data = [[[seg, "orig", None, None, 10] for seg in segments], None, "en"]
    return FakeResponse(text=json.dumps(data, ensure_ascii=False), url=url)


def blocked():
    return FakeResponse(
        status_code=429,
        text="<html>unusual traffic</html>",
        url="https://www.google.com/sorry/index?continue=https://translate.google.com/m",
    )


def upper_echo(url):
    """Translate by upper-casing the text, so tests can predict the exact result."""
    text = query(url)["q"].upper()
    return api_json(text) if is_api(url) else html_page(text)


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.urls = []

    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        return self.handler(url)

    @property
    def html_calls(self):
        return [u for u in self.urls if not is_api(u)]

    @property
    def api_calls(self):
        return [u for u in self.urls if is_api(u)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def google(monkeypatch):
    """Install a fake Google. Call it with a handler(url) -> FakeResponse."""

    def install(handler=upper_echo):
        session = FakeSession(handler)
        monkeypatch.setattr(tr.requests, "Session", lambda: session)
        return session

    return install
