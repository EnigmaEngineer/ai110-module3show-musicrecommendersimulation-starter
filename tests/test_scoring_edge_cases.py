"""Adversarial / edge-case tests for score_song and recommend_songs.

Tests marked xfail(strict=True) document a CONFIRMED bug in the current code. The
suite stays green today and turns red (XPASS) the moment the bug is fixed, which
is the cue to delete the marker.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.recommender import WEIGHTS, load_songs, recommend_songs, score_song  # noqa: E402

CORE_FEATURES = ("genre", "mood", "energy", "valence", "danceability", "acousticness")
MAX_SCORE = sum(WEIGHTS[k] for k in CORE_FEATURES)  # ceiling for profiles that use only these six
SONGS = load_songs(str(ROOT / "data" / "songs.csv"))
BY_TITLE = {s["title"]: s for s in SONGS}
SUNRISE, GYM_HERO = BY_TITLE["Sunrise City"], BY_TITLE["Gym Hero"]


def make_song(**overrides) -> dict:
    song = dict(title="Synthetic", artist="Test", genre="pop", mood="happy",
                energy=0.5, valence=0.5, danceability=0.5, acousticness=0.5)
    song.update(overrides)
    return song


def points(reasons) -> float:
    """Sum the (+x.xx) amounts printed in a reasons list."""
    return sum(float(m) for r in reasons for m in re.findall(r"\(\+(\d+\.\d+)\)", r))


# Each entry: name, user_prefs, hypothesis, failure_mode, what_to_assert.
PROFILES = [
    dict(name="conflict_energy_vs_sad", user_prefs={"energy": 0.9, "mood": "sad"},
         hypothesis="No 'sad' song exists, so mood adds 0; ranking is energy-only. Scorer cannot flag the contradiction.",
         failure_mode="Additive scoring: each feature is independent, no cross-feature consistency check.",
         what_to_assert="Score <= WEIGHTS['energy']; no reason mentions mood."),
    dict(name="conflict_energy_vs_acoustic", user_prefs={"energy": 0.9, "acousticness": 0.95},
         hypothesis="No song satisfies both; winner is a compromise, far below the 2.5 max for these two features.",
         failure_mode="Independent closeness terms; one satisfied feature masks the other.",
         what_to_assert="Best catalog score < energy+acousticness weight (2.5), and no song earns >=90% on both."),
    dict(name="oor_energy_above_1", user_prefs={"energy": 1.5},
         hypothesis="Target is not clamped, so the best possible energy points drop to 1.0 (silent skew, not rejection).",
         failure_mode="_closeness clamps the closeness, never the target.",
         what_to_assert="Every in-range song scores <= 1.0 and >= 0."),
    dict(name="oor_energy_negative", user_prefs={"energy": -0.5},
         hypothesis="Same silent skew in the other direction: max energy points is 1.0.",
         failure_mode="_closeness clamps the closeness, never the target.",
         what_to_assert="Every in-range song scores <= 1.0 and >= 0."),
    dict(name="oor_valence_2", user_prefs={"valence": 2.0},
         hypothesis="Every song is >1.0 away, so the whole profile silently scores 0 with no reasons and no error.",
         failure_mode="`pts > 0` guard swallows the zero; nothing reports an invalid target.",
         what_to_assert="Score 0.0 and empty reasons for every song, no exception."),
    dict(name="type_numeric_string", user_prefs={"energy": "0.8"},
         hypothesis="float('0.8') succeeds, so a string is silently accepted and scores like 0.8.",
         failure_mode="_as_float uses float(), which coerces strings.",
         what_to_assert="Score equals the score for energy=0.8."),
    dict(name="type_non_numeric_string", user_prefs={"energy": "high"},
         hypothesis="float('high') raises ValueError, caught, feature skipped: 0 points, no feedback.",
         failure_mode="_as_float swallows ValueError.",
         what_to_assert="Score 0.0, reasons empty, no exception."),
    dict(name="type_none_values", user_prefs={"energy": None, "genre": None, "mood": None},
         hypothesis="None is skipped everywhere; acts like an empty profile.",
         failure_mode="_as_float(None) -> None; _norm(None) -> ''.",
         what_to_assert="Score 0.0, reasons empty."),
    dict(name="type_bool_energy", user_prefs={"energy": True},
         hypothesis="bool is an int subclass, float(True)==1.0, so True sneaks through as energy 1.0.",
         failure_mode="_as_float has no bool check.",
         what_to_assert="Booleans should be rejected: score 0.0 (currently FAILS)."),
    dict(name="type_nan_inf_strings", user_prefs={"energy": "nan", "valence": "inf", "danceability": float("-inf")},
         hypothesis="Non-finite values are filtered by math.isfinite and ignored.",
         failure_mode="_as_float isfinite guard.",
         what_to_assert="Score 0.0, reasons empty."),
    dict(name="empty_prefs", user_prefs={},
         hypothesis="Nothing to match: (0.0, []) with no exception.",
         failure_mode="Loop bodies all skip on missing keys.",
         what_to_assert="Exactly (0.0, [])."),
    dict(name="none_prefs", user_prefs=None,
         hypothesis="None instead of {} crashes with AttributeError.",
         failure_mode="user_prefs.get is called without a None guard.",
         what_to_assert="Should behave like {} (currently FAILS)."),
    dict(name="genre_only", user_prefs={"genre": "pop"},
         hypothesis="Only exact-genre songs score, all exactly 2.0, so Sunrise City and Gym Hero tie; 'indie pop' gets 0.",
         failure_mode="Exact-match genre, no substring or family logic.",
         what_to_assert="pop songs == 2.0 with one reason; others == 0.0; tie broken by title."),
    dict(name="numeric_only_energy", user_prefs={"energy": 0.5},
         hypothesis="No categorical prefs: only energy reasons, max 2.0.",
         failure_mode="Missing keys skip silently.",
         what_to_assert="Every reason starts with 'energy'; score <= 2.0."),
    dict(name="categorical_ghosts", user_prefs={"genre": "polka", "mood": "ennui"},
         hypothesis="Nothing matches: all scores 0, reasons empty; recommend_songs still returns 'top 5' in alphabetical order.",
         failure_mode="recommend_songs never signals zero-information results.",
         what_to_assert="All scores 0.0, reasons empty, explanation == 'no matching features'."),
    dict(name="mood_mismatch_no_penalty", user_prefs={"genre": "pop", "mood": "sad"},
         hypothesis="Mood miss adds nothing and subtracts nothing.",
         failure_mode="Mood branch only adds.",
         what_to_assert="Sunrise City scores exactly 2.0 with a single genre reason."),
    dict(name="whitespace_internal", user_prefs={"genre": "indie  pop"},
         hypothesis="strip()+lower() don't collapse internal whitespace, so a double space misses 'indie pop'.",
         failure_mode="_norm normalises edges only.",
         what_to_assert="Should match +2.0 (currently FAILS)."),
    dict(name="perfect_match_bait",
         user_prefs={"genre": "pop", "mood": "happy", "energy": 0.9, "valence": 0.9,
                     "danceability": 0.9, "acousticness": 0.0},
         hypothesis="A synthetic song with identical values hits exactly 7.5; no real catalog song comes close.",
         failure_mode="Theoretical max = sum(WEIGHTS) = 7.5.",
         what_to_assert="Synthetic score == 7.5; catalog best < 7.5."),
    dict(name="perfect_anti_match",
         user_prefs={"genre": "pop", "mood": "happy", "energy": 0.0, "valence": 0.0,
                     "danceability": 0.0, "acousticness": 0.0},
         hypothesis="Against a song with opposite genre/mood and all numerics at 1.0: exactly (0.0, []). Unreachable with the real catalog (no song sits at 0 or 1).",
         failure_mode="Closeness floor of 0 and `pts > 0` guard.",
         what_to_assert="Exactly (0.0, [])."),
    dict(name="extremes_all_ones",
         user_prefs={"energy": 1.0, "valence": 1.0, "danceability": 1.0, "acousticness": 1.0},
         hypothesis="Numeric-only ceiling is 4.5; never reaches 7.5.",
         failure_mode="Upper bound of numeric block.",
         what_to_assert="0 <= score <= 4.5 for every song."),
    dict(name="extremes_all_zeros",
         user_prefs={"energy": 0.0, "valence": 0.0, "danceability": 0.0, "acousticness": 0.0},
         hypothesis="Same bounds at the other extreme.",
         failure_mode="Lower bound of numeric block.",
         what_to_assert="0 <= score <= 4.5 for every song."),
    dict(name="boundary_energy_zero",
         user_prefs={"energy": 0.0},
         hypothesis="Against energy=1.0 closeness is 0: no points, no reason, nothing negative leaks in.",
         failure_mode="_closeness lower clamp.",
         what_to_assert="Score for energy-1.0 song is exactly 0.0 and every catalog score >= 0."),
    dict(name="categorical_vs_numeric_dominance",
         user_prefs={"genre": "pop", "mood": "happy", "energy": 0.9, "valence": 0.9,
                     "danceability": 0.9, "acousticness": 0.0},
         hypothesis="Max categorical (3.0) < max numeric (4.5): a wrong-genre, wrong-mood song with perfect numbers beats the right-genre/mood song with terrible numbers.",
         failure_mode="WEIGHTS: genre+mood=3.0 vs numeric=4.5.",
         what_to_assert="Numeric-perfect mismatch (4.5) > categorical-perfect numeric-miss (3.0)."),
    dict(name="duplicate_rows_tie_order",
         user_prefs={"genre": "pop", "energy": 0.8},
         hypothesis="Two identical rows score identically; stable sort keeps input order.",
         failure_mode="Tie-break key is title only.",
         what_to_assert="Equal scores; both returned; order == input order."),
    dict(name="tie_same_title_diff_artist",
         user_prefs={"genre": "pop"},
         hypothesis="Same title, different artist, same score: output order depends on input order, contradicting the 'repeatable' comment.",
         failure_mode="sort key (-score, title) lacks a secondary key such as artist or id.",
         what_to_assert="recommend_songs([a,b]) and recommend_songs([b,a]) return the same order (currently FAILS)."),
    dict(name="float_noise_tie",
         user_prefs={"energy": 0.12},
         hypothesis="Songs at 0.04 and 0.20 are both exactly 0.08 away, a mathematical tie, but 1.84 != 1.8399999999999999, so title tie-break is skipped.",
         failure_mode="Raw float scores compared with == semantics in sorted().",
         what_to_assert="Alphabetically-first title ranks first (currently FAILS)."),
    dict(name="tiny_closeness_zero_reason",
         user_prefs={"acousticness": 1.045},
         hypothesis="Gym Hero (0.05) is 0.995 away: pts=0.0025 > 0 so a reason is emitted, but it prints '(+0.00)'.",
         failure_mode="`pts > 0` guard vs .2f formatting.",
         what_to_assert="No reason contains '(+0.00)' (currently FAILS)."),
    dict(name="wrong_keys",
         user_prefs={"favorite_genre": "pop", "target_energy": 0.9, "likes_acoustic": True},
         hypothesis="UserProfile-style keys are not read by score_song: silent 0, no warning.",
         failure_mode="Unknown keys ignored.",
         what_to_assert="Score 0.0, reasons empty, no exception."),
]
P = {p["name"]: p["user_prefs"] for p in PROFILES}


def scores(prefs, songs=SONGS):
    return [score_song(prefs, s) for s in songs]


# --------------------------------------------------------------------------- #
# Conflicting semantics
# --------------------------------------------------------------------------- #
def test_conflict_energy_vs_sad():
    for score, reasons in scores(P["conflict_energy_vs_sad"]):
        assert score <= WEIGHTS["energy"] + 1e-9
        assert not any(r.startswith("mood") for r in reasons)


def test_conflict_energy_vs_acoustic():
    best = max(s for s, _ in scores(P["conflict_energy_vs_acoustic"]))
    assert best < WEIGHTS["energy"] + WEIGHTS["acousticness"]
    for song in SONGS:
        e = score_song({"energy": 0.9}, song)[0] / WEIGHTS["energy"]
        a = score_song({"acousticness": 0.95}, song)[0] / WEIGHTS["acousticness"]
        assert not (e >= 0.9 and a >= 0.9)


# --------------------------------------------------------------------------- #
# Out-of-range numbers (documents silent skew: target is never clamped)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["oor_energy_above_1", "oor_energy_negative"])
def test_out_of_range_energy_caps_at_half(name):
    for score, _ in scores(P[name]):
        assert 0.0 <= score <= WEIGHTS["energy"] * 0.5 + 1e-9


def test_oor_valence_2_scores_nothing_silently():
    for score, reasons in scores(P["oor_valence_2"]):
        assert score == 0.0 and reasons == []


# --------------------------------------------------------------------------- #
# Type mismatches
# --------------------------------------------------------------------------- #
def test_numeric_string_equals_float():
    assert score_song({"energy": "0.8"}, SUNRISE)[0] == pytest.approx(
        score_song({"energy": 0.8}, SUNRISE)[0])


@pytest.mark.parametrize("name", ["type_non_numeric_string", "type_none_values",
                                  "type_nan_inf_strings", "empty_prefs", "wrong_keys"])
def test_unusable_prefs_score_zero_without_error(name):
    for song in SONGS:
        assert score_song(P[name], song) == (0.0, [])


@pytest.mark.xfail(strict=True, reason="bool passes float(); True is read as energy 1.0")
def test_type_bool_energy_rejected():
    assert score_song(P["type_bool_energy"], GYM_HERO)[0] == 0.0


@pytest.mark.xfail(strict=True, raises=AttributeError, reason="None prefs crash on .get")
def test_none_prefs_behaves_like_empty():
    assert score_song(P["none_prefs"], SUNRISE) == (0.0, [])


# --------------------------------------------------------------------------- #
# Empty / missing / categorical ghosts
# --------------------------------------------------------------------------- #
def test_genre_only_scores_exactly_two_and_ties_by_title():
    for song in SONGS:
        score, reasons = score_song(P["genre_only"], song)
        if song["genre"] == "pop":
            assert score == WEIGHTS["genre"] and len(reasons) == 1
        else:
            assert (score, reasons) == (0.0, [])
    top = recommend_songs(P["genre_only"], SONGS, k=2)
    assert [s["title"] for s, _, _ in top] == ["Gym Hero", "Sunrise City"]


def test_numeric_only_has_no_categorical_reasons():
    for score, reasons in scores(P["numeric_only_energy"]):
        assert score <= WEIGHTS["energy"] + 1e-9
        assert all(r.startswith("energy") for r in reasons)


def test_categorical_ghosts_score_zero_and_say_so():
    assert all(r == (0.0, []) for r in scores(P["categorical_ghosts"]))
    explanations = {e for _, _, e in recommend_songs(P["categorical_ghosts"], SONGS, k=5)}
    assert explanations == {"no matching features"}


def test_mood_mismatch_is_not_penalised():
    score, reasons = score_song(P["mood_mismatch_no_penalty"], SUNRISE)
    assert score == WEIGHTS["genre"] and len(reasons) == 1 and reasons[0].startswith("genre")


# --------------------------------------------------------------------------- #
# Case & whitespace
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("genre", [" POP ", "Pop", "pOp", "\tpop\n", "POP"])
def test_genre_case_and_edge_whitespace_match(genre):
    score, reasons = score_song({"genre": genre}, SUNRISE)
    assert score == WEIGHTS["genre"] and reasons == [f"genre match: 'pop' (+{WEIGHTS['genre']:.2f})"]


@pytest.mark.xfail(strict=True, reason="_norm does not collapse internal whitespace")
def test_internal_whitespace_matches():
    assert score_song(P["whitespace_internal"], BY_TITLE["Rooftop Lights"])[0] == WEIGHTS["genre"]


# --------------------------------------------------------------------------- #
# Perfect / anti / extremes / boundary
# --------------------------------------------------------------------------- #
def test_perfect_match_hits_theoretical_max_and_catalog_does_not():
    assert MAX_SCORE == pytest.approx(sum(WEIGHTS[k] for k in CORE_FEATURES))  # derived, never hardcoded
    twin = make_song(energy=0.9, valence=0.9, danceability=0.9, acousticness=0.0)
    score, reasons = score_song(P["perfect_match_bait"], twin)
    assert score == pytest.approx(MAX_SCORE) and len(reasons) == 6
    assert max(s for s, _ in scores(P["perfect_match_bait"])) < MAX_SCORE


def test_perfect_anti_match_is_exactly_zero():
    anti = make_song(genre="rock", mood="sad", energy=1.0, valence=1.0,
                     danceability=1.0, acousticness=1.0)
    assert score_song(P["perfect_anti_match"], anti) == (0.0, [])


@pytest.mark.parametrize("name", ["extremes_all_ones", "extremes_all_zeros"])
def test_numeric_extremes_stay_within_bounds(name):
    numeric_max = sum(WEIGHTS[k] for k in ("energy", "valence", "danceability", "acousticness"))
    for score, _ in scores(P[name]):
        assert 0.0 <= score <= numeric_max < MAX_SCORE


def test_boundary_energy_zero_never_goes_negative():
    far = make_song(energy=1.0)
    assert score_song(P["boundary_energy_zero"], far) == (0.0, [])
    assert all(s >= 0.0 for s, _ in scores(P["boundary_energy_zero"]))


def test_numeric_perfect_mismatch_beats_categorical_perfect_numeric_miss():
    prefs = P["categorical_vs_numeric_dominance"]
    cat_only = make_song(energy=0.0, valence=0.0, danceability=0.0, acousticness=1.0)
    num_only = make_song(genre="rock", mood="sad", energy=0.9, valence=0.9,
                         danceability=0.9, acousticness=0.0)
    cat_score, num_score = score_song(prefs, cat_only)[0], score_song(prefs, num_only)[0]
    cat_max = WEIGHTS["genre"] + WEIGHTS["mood"]
    num_max = sum(WEIGHTS[k] for k in ("energy", "valence", "danceability", "acousticness"))
    assert cat_max <= cat_score < cat_max + 1.0  # categorical ceiling + small residual closeness
    assert num_score == pytest.approx(num_max)   # numeric ceiling, no categorical points
    assert num_score > cat_score  # documents the weighting; see report


# --------------------------------------------------------------------------- #
# Duplicates and ties
# --------------------------------------------------------------------------- #
def test_duplicate_rows_score_identically_and_keep_input_order():
    a, b = dict(SUNRISE), dict(SUNRISE)
    b["marker"] = "second"
    a["marker"] = "first"
    assert score_song(P["duplicate_rows_tie_order"], a) == score_song(P["duplicate_rows_tie_order"], b)
    top = recommend_songs(P["duplicate_rows_tie_order"], [a, b], k=2)
    assert [s["marker"] for s, _, _ in top] == ["first", "second"]


@pytest.mark.xfail(strict=True, reason="tie-break uses title only; input order leaks through")
def test_same_title_tie_is_order_independent():
    a = make_song(title="Echo", artist="Alpha")
    b = make_song(title="Echo", artist="Beta")
    one = [s["artist"] for s, _, _ in recommend_songs(P["tie_same_title_diff_artist"], [a, b])]
    two = [s["artist"] for s, _, _ in recommend_songs(P["tie_same_title_diff_artist"], [b, a])]
    assert one == two


@pytest.mark.xfail(strict=True, reason="float noise makes a mathematical tie unequal")
def test_float_noise_tie_falls_back_to_title():
    zeta = make_song(title="Zeta", genre="x", mood="x", energy=0.04)
    alpha = make_song(title="Alpha", genre="x", mood="x", energy=0.20)
    top = recommend_songs(P["float_noise_tie"], [zeta, alpha], k=2)
    assert [s["title"] for s, _, _ in top] == ["Alpha", "Zeta"]


# --------------------------------------------------------------------------- #
# Reason-string hygiene
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason="pts > 0 guard allows pts < 0.005, printed as (+0.00)")
def test_no_zero_point_reasons():
    _, reasons = score_song(P["tiny_closeness_zero_reason"], GYM_HERO)
    assert not any("(+0.00)" in r for r in reasons)


# --------------------------------------------------------------------------- #
# Global invariants across every profile x every catalog song
# --------------------------------------------------------------------------- #
DICT_PROFILES = [p for p in PROFILES if isinstance(p["user_prefs"], dict)]
EXTRA_SONGS = [make_song(energy=0.0, valence=0.0, danceability=0.0, acousticness=0.0),
               make_song(energy=1.0, valence=1.0, danceability=1.0, acousticness=1.0)]
ALL_SONGS = SONGS + EXTRA_SONGS


def _cases():
    return [(p["name"], s) for p in DICT_PROFILES for s in ALL_SONGS]


@pytest.mark.parametrize("name,song", _cases(), ids=lambda v: v if isinstance(v, str) else v["title"])
def test_invariants(name, song):
    prefs = P[name]
    score, reasons = score_song(prefs, song)
    assert 0.0 <= score <= MAX_SCORE                                     # 1. non-negative, bounded
    assert abs(points(reasons) - score) <= 0.005 * len(reasons) + 1e-9   # 2. reasons sum to score
    genre_hit = [r for r in reasons if r.startswith("genre")]
    assert all(f"(+{WEIGHTS['genre']:.2f})" in r for r in genre_hit)                        # 3. genre match is exactly WEIGHTS["genre"]
    assert not any(r.startswith("mood") and f"(+{WEIGHTS['mood']:.2f})" not in r for r in reasons)  # 4. mood is all-or-nothing
    assert not any("(-" in r for r in reasons)                           # 6a. no negative points
    if name != "tiny_closeness_zero_reason":                             # known bug, see xfail test above
        assert not any("(+0.00)" in r for r in reasons)                  # 6b. no zero-point reasons


def test_empty_prefs_invariant_for_every_song():
    for song in ALL_SONGS:
        assert score_song({}, song) == (0.0, [])                         # 5.
