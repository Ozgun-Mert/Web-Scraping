"""Offline tests: Google is replaced by the fake in conftest.py."""

import io
import random
import sys

import pytest
import requests

import translate as tr
from conftest import FakeResponse, blocked, is_api, query, upper_echo


# --- Language codes ----------------------------------------------------------

@pytest.mark.parametrize("given, expected", [
    ("tr", "tr"),
    ("TR", "tr"),
    (" de ", "de"),
    ("Turkish", "tr"),
    ("turkish", "tr"),
    ("zh-cn", "zh-CN"),
    ("ZH-TW", "zh-TW"),
    ("zh", "zh-CN"),
    ("he", "iw"),
    ("jv", "jw"),
    ("Chinese (Traditional)", "zh-TW"),
    ("mni-mtei", "mni-Mtei"),
])
def test_resolve_language_accepts_codes_aliases_and_names(given, expected):
    assert tr.resolve_language(given) == expected


@pytest.mark.parametrize("bad", ["xx", "tur", "", "   ", "english!", "auto"])
def test_resolve_language_rejects_unknown_targets(bad):
    with pytest.raises(tr.TranslationError):
        tr.resolve_language(bad)


def test_resolve_language_allows_auto_only_for_source():
    assert tr.resolve_language("auto", allow_auto=True) == "auto"
    assert tr.resolve_language("AUTO", allow_auto=True) == "auto"


def test_resolve_language_suggests_a_close_match():
    with pytest.raises(tr.TranslationError, match="Turkish"):
        tr.resolve_language("turkis")


def test_invalid_target_fails_before_any_request(google):
    session = google()
    with pytest.raises(tr.TranslationError):
        tr.translate("Hello", "xx")
    assert session.urls == []


# --- URL building ------------------------------------------------------------

TRICKY_TEXT = "Tom & Jerry #1: 100% a+b=c? ünïcödé 🍕 / \\ 'q' \"dq\"\nline 2\ttab"


@pytest.mark.parametrize("method", ["html", "api"])
def test_build_url_round_trips_tricky_text(method):
    url = tr.build_url(TRICKY_TEXT, "tr", "auto", method)
    params = query(url)
    assert params["q"] == TRICKY_TEXT
    assert params["tl"] == "tr"
    assert params["sl"] == "auto"
    assert "#" not in url  # a raw '#' would cut the URL off as a fragment


def test_build_url_api_has_required_params():
    params = query(tr.build_url("hi", "de", "en", "api"))
    assert params["client"] == "gtx"
    assert params["dt"] == "t"
    assert tr.build_url("hi", "de", "en", "api").startswith(tr.API_URL)
    assert tr.build_url("hi", "de", "en", "html").startswith(tr.HTML_URL)


# --- Splitting long text -----------------------------------------------------

def test_split_text_empty_and_short():
    assert tr.split_text("") == []
    assert tr.split_text("Hello", limit=50) == ["Hello"]


def random_text(rng, length):
    pieces = [
        "word", "longerword", " ", " ", " ", "\n", "\n\n", ". ", "? ", "!",
        "ünï", "日本語", "。", "🍕", "x" * 30, "\t",
    ]
    out = ""
    while len(out) < length:
        out += rng.choice(pieces)
    return out[:length]


@pytest.mark.parametrize("seed", range(200))
def test_split_text_never_loses_text_and_respects_limit(seed):
    rng = random.Random(seed)
    limit = rng.randint(5, 60)
    text = random_text(rng, rng.randint(0, 400))
    chunks = tr.split_text(text, limit=limit)
    assert "".join(chunks) == text
    assert all(0 < len(chunk) <= limit for chunk in chunks)


def test_split_text_word_without_spaces():
    text = "a" * 125
    chunks = tr.split_text(text, limit=50)
    assert [len(c) for c in chunks] == [50, 50, 25]


def test_split_text_prefers_sentence_ends():
    text = "This is the first one. And here is the second sentence."
    first = tr.split_text(text, limit=40)[0]
    assert first == "This is the first one."


def test_split_text_prefers_cjk_sentence_ends():
    text = "今日はとても良い天気です。明日は雨が降るでしょう。"
    first = tr.split_text(text, limit=20)[0]
    assert first == "今日はとても良い天気です。"


# --- Reading Google's responses ----------------------------------------------

def test_html_result_unescapes_entities(google):
    google(lambda url: FakeResponse(
        text='<div class="result-container">Tom &amp; Jerry &lt;3 &quot;hi&quot;</div>'
    ))
    assert tr.translate("x", "en", method="html") == ('Tom & Jerry <3 "hi"', "html")


def test_api_joins_sentences_and_skips_nulls(google):
    google(lambda url: FakeResponse(
        text='[[["Merhaba. ","Hello. "],[null,null,null,"Merhaba"],["Nasılsın?","How are you?"]],null,"en"]',
        url=url,
    ))
    assert tr.translate("x", "tr", method="api") == ("Merhaba. Nasılsın?", "api")


@pytest.mark.parametrize("body", ["not json", "[]", "[null]", '{"error": 1}', "[[1, 2]]"])
def test_api_malformed_response_is_a_clean_error(google, body):
    google(lambda url: FakeResponse(text=body, url=url))
    with pytest.raises(tr.TranslationError):
        tr.translate("x", "tr", method="api")


def test_blocked_by_status_429(google):
    google(lambda url: FakeResponse(status_code=429, url=url))
    with pytest.raises(tr.BlockedError):
        tr.translate("x", "tr", method="html")


def test_blocked_by_redirect_to_captcha_page(google):
    # Google sometimes serves the CAPTCHA page itself with status 200
    google(lambda url: FakeResponse(url="https://www.google.com/sorry/index?continue=x"))
    with pytest.raises(tr.BlockedError):
        tr.translate("x", "tr", method="html")


def test_server_error_is_not_reported_as_blocked(google):
    google(lambda url: FakeResponse(status_code=500, url=url))
    with pytest.raises(tr.TranslationError, match="500") as info:
        tr.translate("x", "tr", method="api")
    assert not isinstance(info.value, tr.BlockedError)


def test_network_error_is_a_clean_error(google):
    def fail(url):
        raise requests.ConnectionError("no internet")

    google(fail)
    with pytest.raises(tr.TranslationError, match="Could not reach"):
        tr.translate("x", "tr")


# --- Choosing html or api ----------------------------------------------------

def test_empty_text_makes_no_request(google):
    session = google()
    for text in ["", "   ", "\n\n\t"]:
        with pytest.raises(tr.TranslationError, match="Nothing"):
            tr.translate(text, "tr")
    assert session.urls == []


def test_auto_uses_html_when_it_works(google):
    session = google()
    assert tr.translate("hello", "tr") == ("HELLO", "html")
    assert session.api_calls == []


def test_auto_falls_back_to_api_when_blocked(google):
    session = google(lambda url: upper_echo(url) if is_api(url) else blocked())
    assert tr.translate("hello", "tr") == ("HELLO", "api")


def test_auto_stops_trying_html_after_first_block(google, monkeypatch):
    monkeypatch.setattr(tr, "MAX_CHUNK_CHARS", 20)
    session = google(lambda url: upper_echo(url) if is_api(url) else blocked())
    text = "One sentence here. " * 10
    translation, used = tr.translate(text, "tr")
    assert translation == text.strip().upper()
    assert used == "api"
    assert len(session.html_calls) == 1
    assert len(session.api_calls) > 1


def test_auto_falls_back_when_html_layout_changed(google):
    session = google(lambda url: upper_echo(url) if is_api(url)
                     else FakeResponse(text="<div class='something-new'>?</div>"))
    assert tr.translate("hello", "tr") == ("HELLO", "api")


def test_html_only_does_not_fall_back(google):
    session = google(lambda url: upper_echo(url) if is_api(url) else blocked())
    with pytest.raises(tr.BlockedError):
        tr.translate("hello", "tr", method="html")
    assert session.api_calls == []


def test_api_only_never_touches_html(google):
    session = google()
    assert tr.translate("hello", "tr", method="api") == ("HELLO", "api")
    assert session.html_calls == []


def test_sends_source_and_target_codes(google):
    session = google()
    tr.translate("Gift", "English", source="DE")
    params = query(session.urls[0])
    assert (params["sl"], params["tl"]) == ("de", "en")


# --- Keeping the shape of long texts -----------------------------------------

@pytest.fixture
def small_chunks(monkeypatch):
    monkeypatch.setattr(tr, "MAX_CHUNK_CHARS", 30)


def test_long_paragraph_is_not_broken_into_lines(google, small_chunks):
    session = google()
    text = "This is a long paragraph that will need many requests to translate fully."
    translation, _ = tr.translate(text, "tr")
    assert len(session.urls) > 1
    assert translation == text.upper()


def test_blank_lines_between_paragraphs_are_kept(google, small_chunks):
    google()
    text = "First paragraph is here.\n\nSecond paragraph is here.\n\n\nThird one."
    assert tr.translate(text, "tr")[0] == text.upper()


def test_word_cut_in_the_middle_is_joined_back(google, small_chunks):
    google()
    text = "x" * 75
    assert tr.translate(text, "tr")[0] == text.upper()


def test_whitespace_only_chunks_are_not_sent(google, small_chunks):
    session = google()
    text = "a" * 30 + "\n" * 40 + "b"
    tr.translate(text, "tr")
    assert all(query(u)["q"].strip() for u in session.urls)


# --- Command line ------------------------------------------------------------

def run_cli(monkeypatch, capsys, *args, stdin=None):
    monkeypatch.setattr(sys, "argv", ["translate.py", *args])
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", stdin)
    code = 0
    try:
        tr.main()
    except SystemExit as exc:
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


class TTY(io.StringIO):
    def isatty(self):
        return True


def test_cli_text_argument(google, monkeypatch, capsys):
    google()
    code, out, err = run_cli(monkeypatch, capsys, "Hello there", "--to", "tr", stdin=TTY())
    assert (code, out.strip(), err) == (0, "HELLO THERE", "")


def test_cli_reads_stdin(google, monkeypatch, capsys):
    google()
    code, out, _ = run_cli(monkeypatch, capsys, "--to", "en", stdin=io.StringIO("Günaydın\n"))
    assert (code, out.strip()) == (0, "GÜNAYDIN")


def test_cli_reads_utf8_file_with_bom(google, monkeypatch, capsys, tmp_path):
    session = google()
    path = tmp_path / "notes.txt"
    path.write_bytes("﻿Çok güzel".encode("utf-8"))
    code, out, _ = run_cli(monkeypatch, capsys, "--file", str(path), "--to", "en", stdin=TTY())
    assert code == 0
    assert query(session.urls[0])["q"] == "Çok güzel"


def test_cli_missing_file_is_a_clean_error(google, monkeypatch, capsys, tmp_path):
    google()
    code, out, err = run_cli(
        monkeypatch, capsys, "--file", str(tmp_path / "nope.txt"), "--to", "en", stdin=TTY()
    )
    assert code == 1
    assert "Error" in err and "Traceback" not in err


def test_cli_invalid_language_is_a_clean_error(google, monkeypatch, capsys):
    session = google()
    code, out, err = run_cli(monkeypatch, capsys, "Hello", "--to", "tur", stdin=TTY())
    assert code == 1
    assert "Error" in err and out == ""
    assert session.urls == []


def test_cli_without_input_shows_usage(google, monkeypatch, capsys):
    google()
    code, _, err = run_cli(monkeypatch, capsys, "--to", "tr", stdin=TTY())
    assert code == 2
    assert "usage" in err


def test_cli_reports_fallback_and_url(google, monkeypatch, capsys):
    google(lambda url: upper_echo(url) if is_api(url) else blocked())
    code, out, err = run_cli(monkeypatch, capsys, "hi", "--to", "tr", "--show-url", stdin=TTY())
    assert code == 0
    assert "blocked" in err
    assert tr.API_URL in out and out.strip().endswith("HI")


def test_cli_google_failure_exits_1(google, monkeypatch, capsys):
    google(lambda url: FakeResponse(status_code=503, url=url))
    code, out, err = run_cli(monkeypatch, capsys, "hi", "--to", "tr", stdin=TTY())
    assert code == 1 and "503" in err and out == ""
