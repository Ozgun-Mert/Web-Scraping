"""Live tests: real requests to Google. Run with `pytest -m live`.

Translations can vary a little over time, so each check accepts a few
correct answers and looks for key words instead of an exact sentence.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

import translate as tr

pytestmark = pytest.mark.live

SCRIPT = Path(__file__).resolve().parent.parent / "translate.py"


@pytest.fixture(autouse=True)
def pause_between_requests():
    """Be gentle with Google so the tests don't get rate-limited."""
    yield
    time.sleep(0.5)


def run(text, target, source="auto"):
    translation, _ = tr.translate(text, target, source)
    return translation


def fold(text):
    """Lower-case for comparing. Python lower-cases Turkish 'İ' to 'i' plus a
    combining dot (U+0307), which would stop 'İyi' from matching 'iyi'."""
    return text.lower().replace("̇", "")


@pytest.mark.parametrize("text, source, target, any_of", [
    # False friend: in German "Gift" means poison, not present
    ("Gift", "de", "en", ["poison"]),
    # One of the longest Turkish words (agglutination)
    ("Çekoslovakyalılaştıramadıklarımızdan mısınız?", "tr", "en", ["czechoslovak"]),
    # Long German compound noun
    ("Der Kühlschrankmagnet ist kaputt.", "de", "en", ["refrigerator magnet", "fridge magnet"]),
    # Source language detected automatically
    ("¿Dónde está la biblioteca?", "auto", "en", ["library"]),
    ("Привет, как дела?", "auto", "en", ["hello", "hi"]),
    # Non-Latin scripts: Japanese, Arabic (right-to-left), Greek
    ("猫が好きです。", "auto", "en", ["cat"]),
    ("شكرا جزيلا لك", "auto", "en", ["thank"]),
    ("Καλημέρα", "auto", "en", ["good morning"]),
    # Into non-Latin scripts and Turkish characters
    ("Good morning", "en", "zh-CN", ["早上好", "早安"]),
    ("Good morning", "en", "zh-TW", ["早安", "早上好"]),
    ("Thank you very much", "en", "ar", ["شكرا"]),
    ("I will go to the market tomorrow morning.", "en", "tr", ["yarın"]),
    # Language names and aliases instead of codes
    ("Good night", "english", "Turkish", ["iyi geceler"]),
    ("Thank you", "en", "he", ["תודה"]),
    # Already in the target language
    ("Merhaba dünya", "tr", "tr", ["merhaba dünya"]),
])
def test_hard_translations(text, source, target, any_of):
    result = fold(run(text, target, source))
    assert any(fold(option) in result for option in any_of), result


def test_emoji_survive():
    result = run("I love pizza 🍕 and coffee ☕", "de")
    assert "🍕" in result and "☕" in result, result


def test_numbers_and_times_survive():
    result = run("The meeting is on 15 March 2025 at 14:30.", "de")
    for part in ["15", "2025", "14:30"]:
        assert part in result, result


def test_url_special_characters_do_not_cut_the_text():
    # '&', '#', '%' and '+' all have special meaning in URLs
    result = run("Tom & Jerry: 100% fun? #1 for a+b", "es").lower()
    for part in ["jerry", "100", "#1", "a+b"]:
        assert part in result, result


def test_lines_are_kept():
    result = run("Good morning.\nGood evening.\nGood night.", "de")
    assert len(result.splitlines()) == 3, result


def test_paragraph_breaks_are_kept():
    result = run("This is the first paragraph.\n\nThis is the second paragraph.", "de")
    assert "\n\n" in result, result


def test_long_paragraph_needs_several_requests_and_stays_one_paragraph():
    sentences = [
        "The weather was beautiful this morning.",
        "My neighbour planted new flowers in her garden.",
        "We talked about the football match from last night.",
        "Later I went to the library to return some books.",
    ]
    text = " ".join(sentences * 20)  # about 3600 characters, no line breaks
    assert len(tr.split_text(text, tr.MAX_CHUNK_CHARS)) > 1
    result = run(text, "tr")
    assert "\n" not in result, "a single paragraph came back split into lines"
    assert len(result) > len(text) * 0.6, len(result)
    assert "kütüphane" in fold(result)


def test_long_japanese_text_fits_in_url():
    # Each Japanese character becomes 9 characters in the URL, so this is the
    # hardest case for URL length.
    text = "今日はとても良い天気です。" * 110  # about 1400 characters
    result = run(text, "en").lower()
    assert result.count("weather") >= 100, result[:200]


def test_html_like_text_is_translated_not_interpreted():
    result = run("<b>Hello</b> world & friends", "de")
    assert "<b>" in result and "</b>" in result, result


def test_cli_end_to_end_with_utf8_pipe():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--to", "en"],
        input="Günaydın, nasılsın?".encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    out = proc.stdout.decode("utf-8").lower()
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert "good morning" in out, out


def test_cli_end_to_end_argument_and_codes():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "Ich habe Hunger", "--from", "DE", "--to", "EN"],
        capture_output=True,
        timeout=60,
    )
    out = proc.stdout.decode("utf-8").lower()
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert "hungry" in out, out
