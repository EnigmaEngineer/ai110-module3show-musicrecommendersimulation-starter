"""Tests for get_top_recommendations (greedy selection with a diversity penalty)."""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.main import PROFILES, main  # noqa: E402
from src.recommender import STRATEGIES, get_top_recommendations, load_songs, recommend_songs  # noqa: E402

SONGS = load_songs(str(ROOT / "data" / "songs.csv"))
PREFS = {"energy": 0.5}  # with the default weights: base score = 4.0 * (1 - |energy - 0.5|)


def song(title, artist, genre, energy):
    return dict(title=title, artist=artist, genre=genre, energy=energy)


def titles(rows):
    return [s["title"] for s, _, _ in rows]


# ---- the penalty rules ------------------------------------------------------
def test_artist_repeat_is_pushed_below_a_fresh_artist():
    pool = [song("X1", "X", "g1", 0.50), song("X2", "X", "g2", 0.52), song("Y1", "Y", "g3", 0.60)]
    assert titles(recommend_songs(PREFS, pool, 2)) == ["X1", "X2"]              # plain: X takes both
    assert titles(get_top_recommendations(PREFS, pool, 2, mode=None)) == ["X1", "Y1"]


def test_penalized_pick_shows_reason_and_adjusted_score():
    pool = [song("X1", "X", "g1", 0.50), song("X2", "X", "g2", 0.52),
            song("Y1", "Y", "g3", 0.60), song("Z1", "Z", "g4", 0.70)]
    rows = get_top_recommendations(PREFS, pool, 4, mode=None)
    assert titles(rows) == ["X1", "Y1", "Z1", "X2"]
    _, score, explanation = rows[3]
    assert score == pytest.approx(3.92 - 1.5)
    assert "diversity penalty (artist duplicate): -1.50" in explanation.split("; ")
    assert "diversity" not in rows[0][2]  # the first pick is never penalized


def test_genre_repeat_penalty():
    pool = [song("G1", "A", "pop", 0.50), song("G2", "B", "pop", 0.52), song("H", "C", "rock", 0.60)]
    assert titles(get_top_recommendations(PREFS, pool, 2, mode=None)) == ["G1", "H"]
    _, score, explanation = get_top_recommendations(PREFS, pool, 3, mode=None)[2]
    assert score == pytest.approx(3.92 - 1.0)
    assert "diversity penalty (genre duplicate): -1.00" in explanation


def test_artist_and_genre_penalties_stack_and_list_artist_first():
    pool = [song("P1", "X", "pop", 0.50), song("P2", "X", "pop", 0.52)]
    _, score, explanation = get_top_recommendations(PREFS, pool, 2, mode=None)[1]
    assert score == pytest.approx(3.92 - 2.5)
    assert explanation.split("; ")[-2:] == ["diversity penalty (artist duplicate): -1.50",
                                            "diversity penalty (genre duplicate): -1.00"]


def test_penalty_applies_once_not_per_earlier_pick():
    pool = [song("X1", "X", "g1", 0.50), song("X2", "X", "g2", 0.52), song("X3", "X", "g3", 0.54)]
    rows = get_top_recommendations(PREFS, pool, 3, mode=None)
    assert [round(r[1], 2) for r in rows] == [4.0, 3.92 - 1.5, 3.84 - 1.5]
    assert rows[2][2].count("artist duplicate") == 1


def test_penalty_is_a_nudge_not_a_quota():
    pool = [song("X1", "X", "g1", 0.50), song("X2", "X", "g2", 0.51), song("Y1", "Y", "g3", 0.90)]
    # X2 is 3.96 - 1.5 = 2.46, still above Y1 at 1.6, so one artist keeps both slots
    assert titles(get_top_recommendations(PREFS, pool, 2, mode=None)) == ["X1", "X2"]


def test_matching_ignores_case_and_edge_spaces():
    pool = [song("A", "Neon Echo", "pop", 0.50), song("B", " neon ECHO ", "rock", 0.52)]
    assert "artist duplicate" in get_top_recommendations(PREFS, pool, 2, mode=None)[1][2]


def test_blank_or_missing_artist_and_genre_are_not_duplicates():
    pool = [song("A", "", "", 0.50), song("B", None, None, 0.52), dict(title="C", energy=0.54)]
    rows = get_top_recommendations(PREFS, pool, 3, mode=None)
    assert all("diversity" not in r[2] for r in rows)


def test_zero_penalties_reproduce_the_plain_ranking():
    for prefs in PROFILES.values():
        for mode in (None, *STRATEGIES):
            plain = recommend_songs(prefs, SONGS, 5, mode)
            same = get_top_recommendations(prefs, SONGS, 5, mode, artist_penalty=0, genre_penalty=0)
            assert [(s["title"], sc, e) for s, sc, e in same] == [(s["title"], sc, e) for s, sc, e in plain]


# ---- n, modes and bad input --------------------------------------------------
@pytest.mark.parametrize("n", [0, -3])
def test_non_positive_n_gives_nothing(n):
    assert get_top_recommendations(PROFILES["Chill Lofi"], SONGS, n) == []


def test_asking_for_more_than_exist_returns_each_song_once():
    rows = get_top_recommendations(PROFILES["Chill Lofi"], SONGS, 100)
    assert sorted(titles(rows)) == sorted(s["title"] for s in SONGS)


def test_default_mode_is_genre_first():
    prefs = PROFILES["Conflicted Listener"]
    assert get_top_recommendations(prefs, SONGS) == get_top_recommendations(prefs, SONGS, 5, "genre_first")


@pytest.mark.parametrize("kwargs", [{"mode": "polka"}, {"artist_penalty": -1}, {"genre_penalty": -0.1}])
def test_bad_arguments_raise(kwargs):
    with pytest.raises(ValueError):
        get_top_recommendations({}, [], **kwargs)


def test_inputs_are_not_mutated():
    prefs, pool = copy.deepcopy(PROFILES["High-Energy Pop"]), copy.deepcopy(SONGS)
    get_top_recommendations(prefs, pool, 5)
    assert prefs == PROFILES["High-Energy Pop"] and pool == SONGS


# ---- what it really does on the 10-song catalog ----------------------------------
def test_high_energy_pop_gym_hero_takes_a_genre_penalty_and_rooftop_lights_moves_up():
    rows = get_top_recommendations(PROFILES["High-Energy Pop"], SONGS, 5, mode=None)
    assert titles(rows)[:3] == ["Sunrise City", "Rooftop Lights", "Gym Hero"]
    assert "diversity penalty (genre duplicate): -1.00" in rows[2][2]
    assert rows[2][1] == pytest.approx(7.29 - 1.0, abs=0.01)


def test_small_catalog_limit_a_repeated_artist_can_survive():
    # Neon Echo has 2 of the 10 songs; even with -1.50, Night Drive Loop still makes the top 5.
    rows = get_top_recommendations(PROFILES["High-Energy Pop"], SONGS, 5, mode=None)
    assert titles(rows)[4] == "Night Drive Loop"
    assert "diversity penalty (artist duplicate): -1.50" in rows[4][2]


def test_trade_off_a_poor_energy_match_can_enter_the_list():
    # Deep Intense Rock wants energy 0.92; Midnight Coding sits at 0.42 but is a fresh artist and genre.
    plain = titles(recommend_songs(PROFILES["Deep Intense Rock"], SONGS, 5))
    diverse = titles(get_top_recommendations(PROFILES["Deep Intense Rock"], SONGS, 5, mode=None))
    assert "Midnight Coding" not in plain and "Midnight Coding" in diverse


# ---- command line --------------------------------------------------------------
def test_cli_uses_diversity_by_default_and_flag_turns_it_off(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    main([])
    assert "diversity penalty" in capsys.readouterr().out
    main(["--no-diversity"])
    assert "diversity penalty" not in capsys.readouterr().out
