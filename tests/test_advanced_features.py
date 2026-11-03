"""Tests for the advanced song features: popularity, release_decade,
detailed_mood_tags, instrumentalness and speechiness."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.recommender import WEIGHTS, load_songs, score_song  # noqa: E402

HEADER = ("id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness,"
          "popularity,release_decade,detailed_mood_tags,instrumentalness,speechiness")


def write_csv(tmp_path, *rows, header=HEADER):
    path = tmp_path / "songs.csv"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return str(path)


def make_song(**overrides):
    song = dict(title="S", genre="pop", mood="happy", energy=0.5, valence=0.5,
                danceability=0.5, acousticness=0.5, popularity=80, release_decade=1990,
                detailed_mood_tags=["euphoric", "dance"], instrumentalness=0.5, speechiness=0.5)
    song.update(overrides)
    return song


# ---- load_songs ------------------------------------------------------------
def test_loader_parses_new_columns_with_correct_types(tmp_path):
    path = write_csv(tmp_path, '1,A,x,pop,happy,0.8,120,0.8,0.8,0.2,78,2020,"nostalgic, Chill",0.02,0.05')
    (song,) = load_songs(path)
    assert song["popularity"] == 78 and isinstance(song["popularity"], int)
    assert song["release_decade"] == 2020 and isinstance(song["release_decade"], int)
    assert song["instrumentalness"] == 0.02 and isinstance(song["instrumentalness"], float)
    assert song["speechiness"] == 0.05 and isinstance(song["speechiness"], float)
    assert song["detailed_mood_tags"] == ["nostalgic", "chill"]


def test_loader_blank_new_cells_keep_the_row(tmp_path):
    path = write_csv(tmp_path, "1,A,x,pop,happy,0.8,120,0.8,0.8,0.2,,,,,")
    (song,) = load_songs(path)
    assert song["popularity"] is None and song["release_decade"] is None
    assert song["instrumentalness"] is None and song["speechiness"] is None
    assert song["detailed_mood_tags"] == []


def test_loader_still_works_without_the_new_columns(tmp_path):
    path = write_csv(tmp_path, "1,A,x,pop,happy,0.8,120,0.8,0.8,0.2",
                     header="id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness")
    (song,) = load_songs(path)
    assert "popularity" not in song and "detailed_mood_tags" not in song


@pytest.mark.parametrize("bad", ["abc", "8.5"])
def test_loader_skips_row_with_unparseable_popularity(tmp_path, bad):
    path = write_csv(tmp_path, f"1,A,x,pop,happy,0.8,120,0.8,0.8,0.2,{bad},2020,,0.1,0.1",
                     "2,B,x,pop,happy,0.8,120,0.8,0.8,0.2,50,2020,,0.1,0.1")
    assert [s["title"] for s in load_songs(path)] == ["B"]


def test_loader_tag_cleanup(tmp_path):
    path = write_csv(tmp_path, '1,A,x,pop,happy,0.8,120,0.8,0.8,0.2,50,2020," a , ,B,a ",0.1,0.1')
    assert load_songs(path)[0]["detailed_mood_tags"] == ["a", "b"]


# ---- popularity ------------------------------------------------------------
def test_popularity_80_vs_90_matches_the_requested_example():
    score, reasons = score_song({"popularity": 90}, make_song(popularity=80))
    assert score == pytest.approx(0.45)
    assert reasons == ["popularity 80 vs target 90 (+0.45)"]


def test_popularity_80_vs_100_is_040():
    assert score_song({"popularity": 100}, make_song(popularity=80))[0] == pytest.approx(0.40)


def test_popularity_exact_gets_full_weight_and_far_apart_gets_nothing():
    assert score_song({"popularity": 50}, make_song(popularity=50))[0] == pytest.approx(WEIGHTS["popularity"])
    assert score_song({"popularity": 0}, make_song(popularity=100)) == (0.0, [])


def test_popularity_skipped_when_song_has_none():
    assert score_song({"popularity": 50}, make_song(popularity=None)) == (0.0, [])


# ---- release decade --------------------------------------------------------
def test_decade_exact_match_only():
    score, reasons = score_song({"release_decade": 1990}, make_song(release_decade=1990))
    assert score == WEIGHTS["release_decade"] and reasons == ["release decade match: 1990s (+0.50)"]
    assert score_song({"release_decade": 1990}, make_song(release_decade=2000)) == (0.0, [])


def test_decade_accepts_numeric_string_target():
    assert score_song({"release_decade": "1990"}, make_song(release_decade=1990))[0] == WEIGHTS["release_decade"]


# ---- detailed mood tags ----------------------------------------------------
def test_tags_single_overlap_is_025():
    score, reasons = score_song({"detailed_mood_tags": ["happy", "euphoric"]}, make_song())
    assert score == pytest.approx(0.25) and reasons == ["tag matches: euphoric (+0.25)"]


def test_tags_two_overlaps_is_050_and_keeps_user_order():
    song = make_song(detailed_mood_tags=["chill", "nostalgic", "sleepy"])
    score, reasons = score_song({"detailed_mood_tags": ["Nostalgic", " chill "]}, song)
    assert score == pytest.approx(0.50) and reasons == ["tag matches: nostalgic, chill (+0.50)"]


def test_tags_accept_comma_string_and_ignore_duplicates():
    song = make_song(detailed_mood_tags="euphoric, dance")
    score, _ = score_song({"detailed_mood_tags": "dance, DANCE, euphoric"}, song)
    assert score == pytest.approx(0.50)


@pytest.mark.parametrize("wanted", [None, [], "", 5, [None, ""], {"a": 1}])
def test_tags_unusable_or_empty_prefs_score_nothing(wanted):
    assert score_song({"detailed_mood_tags": wanted}, make_song()) == (0.0, [])


@pytest.mark.parametrize("have", [None, [], "", 7])
def test_tags_missing_on_song_score_nothing(have):
    assert score_song({"detailed_mood_tags": ["euphoric"]}, make_song(detailed_mood_tags=have)) == (0.0, [])


# ---- instrumentalness / speechiness ---------------------------------------
@pytest.mark.parametrize("field", ["instrumentalness", "speechiness"])
def test_closeness_features_use_standard_formula(field):
    score, reasons = score_song({field: 0.9}, make_song(**{field: 0.7}))
    assert score == pytest.approx(WEIGHTS[field] * 0.8)
    assert reasons == [f"{field} 0.70 vs target 0.90 (+{WEIGHTS[field] * 0.8:.2f})"]


# ---- whole-profile sanity --------------------------------------------------
def test_full_perfect_match_hits_the_documented_ceiling():
    prefs = dict(genre="pop", mood="happy", energy=0.5, valence=0.5, danceability=0.5, acousticness=0.5,
                 instrumentalness=0.5, speechiness=0.5, popularity=80, release_decade=1990,
                 detailed_mood_tags=["euphoric", "dance"])
    score, reasons = score_song(prefs, make_song())
    fixed = ("genre", "mood", "energy", "valence", "danceability", "acousticness",
             "instrumentalness", "speechiness", "popularity", "release_decade")
    expected = sum(WEIGHTS[k] for k in fixed) + 2 * WEIGHTS["tag_match"]
    assert score == pytest.approx(expected)
    assert len(reasons) == 11


def test_old_profiles_unaffected_by_new_columns():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    assert score_song(prefs, make_song(popularity=None, detailed_mood_tags=[])) == score_song(prefs, make_song())
