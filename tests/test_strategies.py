"""Tests for the scoring strategies (Strategy pattern) and the --mode switch."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.main import main  # noqa: E402
from src.recommender import (  # noqa: E402
    STRATEGIES, WEIGHTS, ScoringStrategy, WeightedScoringStrategy,
    load_songs, recommend_songs, score_song,
)

SONGS = load_songs(str(ROOT / "data" / "songs.csv"))
SONG = dict(title="S", genre="pop", mood="happy", energy=0.5, valence=0.5, danceability=0.5, acousticness=0.5)

# mode -> (genre weight, mood weight, energy weight), as specified
EXPECTED = {
    "genre_first": (3.0, 1.0, 1.0),
    "mood_first": (1.0, 3.0, 1.0),
    "energy_focused": (1.0, 1.0, 4.0),
}


@pytest.mark.parametrize("mode,weights", EXPECTED.items())
def test_each_strategy_uses_its_weights(mode, weights):
    genre_w, mood_w, energy_w = weights
    assert score_song({"genre": "pop"}, SONG, mode)[0] == genre_w
    assert score_song({"mood": "happy"}, SONG, mode)[0] == mood_w
    assert score_song({"energy": 0.5}, SONG, mode)[0] == energy_w


@pytest.mark.parametrize("mode", EXPECTED)
def test_strategies_leave_the_other_weights_alone(mode):
    for field in ("valence", "danceability", "acousticness"):
        assert score_song({field: 0.5}, SONG, mode)[0] == WEIGHTS[field]


@pytest.mark.parametrize("mode", EXPECTED)
def test_reason_strings_show_the_strategy_points(mode):
    genre_w, mood_w, _ = EXPECTED[mode]
    _, reasons = score_song({"genre": "pop", "mood": "happy"}, SONG, mode)
    assert reasons == [f"genre match: 'pop' (+{genre_w:.2f})", f"mood match: 'happy' (+{mood_w:.2f})"]


def test_no_mode_matches_energy_focused_and_the_raw_weights():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.9, "valence": 0.8}
    assert score_song(prefs, SONG) == score_song(prefs, SONG, "energy_focused")
    assert score_song(prefs, SONG) == score_song(prefs, SONG, None)
    for profile_rank in zip(recommend_songs(prefs, SONGS), recommend_songs(prefs, SONGS, mode="energy_focused")):
        assert profile_rank[0] == profile_rank[1]


@pytest.mark.parametrize("spelling", ["MOOD_FIRST", " mood-first ", "Mood First"])
def test_mode_names_are_forgiving(spelling):
    assert score_song({"mood": "happy"}, SONG, spelling)[0] == 3.0


def test_strategy_object_is_accepted():
    assert score_song({"mood": "happy"}, SONG, STRATEGIES["mood_first"])[0] == 3.0


@pytest.mark.parametrize("bad", ["polka", "", "genre", 7])
def test_unknown_mode_raises_instead_of_falling_back(bad):
    with pytest.raises(ValueError, match="unknown scoring mode"):
        score_song({"genre": "pop"}, SONG, bad)
    with pytest.raises(ValueError):
        recommend_songs({}, [], mode=bad)  # fails even with nothing to score


def test_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ScoringStrategy()


def test_changing_the_mode_changes_who_is_second_for_happy_pop():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.9, "valence": 0.8, "danceability": 0.85, "acousticness": 0.1}
    second = lambda mode: recommend_songs(prefs, SONGS, 5, mode)[1][0]["title"]
    assert second("genre_first") == "Gym Hero"        # pop, but intense
    assert second("mood_first") == "Rooftop Lights"   # indie pop, but happy


def test_new_mode_needs_no_change_to_score_song():
    class ShortestTitleFirst(ScoringStrategy):
        def score(self, user_prefs, song):
            return 100.0 - len(song["title"]), ["shorter is better"]

    top = recommend_songs({}, SONGS, 1, mode=ShortestTitleFirst())
    assert top[0][0]["title"] == min((s["title"] for s in SONGS), key=len)
    assert top[0][2] == "shorter is better"


def test_a_subclass_with_overrides_is_all_a_new_weighting_takes():
    class ValenceFirst(WeightedScoringStrategy):
        overrides = {"valence": 5.0}

    assert score_song({"valence": 0.5}, SONG, ValenceFirst())[0] == 5.0


def test_strategies_follow_edits_to_weights(monkeypatch):
    monkeypatch.setitem(WEIGHTS, "valence", 0.0)
    assert score_song({"valence": 0.5}, SONG, "genre_first") == (0.0, [])
    assert score_song({"valence": 0.5}, SONG) == (0.0, [])


# ---- command line -----------------------------------------------------------
def test_cli_mode_flag_selects_the_strategy(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    main(["--mode", "mood_first"])
    out = capsys.readouterr().out
    assert "Scoring mode: mood_first" in out
    assert "mood match: 'happy' (+3.00)" in out


def test_cli_without_flag_is_the_default_output(monkeypatch, capsys):
    monkeypatch.chdir(ROOT)
    main([])
    assert "Scoring mode" not in capsys.readouterr().out


def test_cli_rejects_unknown_mode(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--mode", "polka"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
