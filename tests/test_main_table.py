"""Tests for the tabulate-based output in src/main.py."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.main import HEADERS, PROFILES, REASON_WIDTH, build_rows, main, print_recommendations  # noqa: E402
from src.recommender import get_top_recommendations, load_songs  # noqa: E402

SONGS = load_songs(str(ROOT / "data" / "songs.csv"))


@pytest.fixture
def output(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    main([])
    return capsys.readouterr().out


def table_lines(text):
    return [line for line in text.splitlines() if line.startswith(("+", "|"))]


def test_every_table_line_has_the_same_width_per_table(output):
    chunks = output.split("TOP 5 RECOMMENDATIONS")[1:]  # one chunk per profile's table
    assert len(chunks) == len(PROFILES)
    for chunk in chunks:
        lines = table_lines(chunk.split("\nProfile:")[0])
        assert lines and len({len(line) for line in lines}) == 1


def test_each_profile_shows_five_numbered_rows_and_the_headers(output):
    assert len(re.findall(r"^\|\s+[1-5] \|", output, flags=re.M)) == 5 * len(PROFILES)
    for header in HEADERS:
        assert output.count(header) >= len(PROFILES)


def test_output_is_plain_ascii_and_has_no_python_list_repr(output):
    assert output.isascii()
    assert "['" not in output and '["' not in output


def test_reasons_are_one_per_line_in_the_cell(output):
    assert re.search(r"\| genre match: 'pop' \(\+1\.00\)\s+\|\n\|\s+\|\s+\|\s+\|\s+\| mood match: 'happy'", output)


def test_scores_print_with_two_decimals():
    rows = build_rows([({"title": "T", "artist": "A"}, 7.2, "x")])
    assert rows == [[1, "T", "A", 7.2, "x"]]


def test_score_column_shows_trailing_zero(capsys):
    print_recommendations("P", {"energy": 0.5}, [({"title": "T", "artist": "A"}, 7.2, "x")])
    assert " 7.20 " in capsys.readouterr().out


def test_no_matching_reasons_gives_a_filled_cell():
    rows = build_rows(get_top_recommendations({}, SONGS, 1))
    assert rows[0][4] == "no matching features"


def test_long_reason_wraps_instead_of_widening_the_table():
    long_reason = "tag matches: " + ", ".join(f"tag{i}" for i in range(20)) + " (+5.00)"
    (row,) = build_rows([({"title": "T", "artist": "A"}, 5.0, long_reason + "; genre match: 'pop' (+1.00)")])
    lines = row[4].split("\n")
    assert all(len(line) <= REASON_WIDTH for line in lines)
    assert lines[-1] == "genre match: 'pop' (+1.00)"


def test_empty_recommendations_print_a_message(capsys):
    print_recommendations("P", {}, [])
    out = capsys.readouterr().out
    assert "No songs to recommend" in out and "+--" not in out
