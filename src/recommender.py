from __future__ import annotations

import csv
import logging
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Columns converted to numbers when loading songs.csv. Any other column stays a string.
FLOAT_COLUMNS = ("energy", "tempo_bpm", "valence", "danceability", "acousticness")
INT_COLUMNS = ("id", "duration_sec", "year")
# These must be present and valid, or the row is skipped. The other numeric
# columns are converted only when the CSV has them.
REQUIRED_COLUMNS = ("id",) + FLOAT_COLUMNS
# Optional feature columns. A column the CSV lacks, or a blank cell, means
# "unknown": the song is simply not scored on that feature. A non-blank cell
# that can't be parsed skips the row, like the required columns.
OPTIONAL_INT_COLUMNS = ("popularity", "release_decade")
OPTIONAL_FLOAT_COLUMNS = ("instrumentalness", "speechiness")
TAGS_COLUMN = "detailed_mood_tags"

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        # TODO: Implement explanation logic
        return "Explanation placeholder"

def _to_number(value: Optional[str], kind: type) -> float:
    """Convert a CSV string to `kind` (int or float). Raises ValueError if it can't."""
    if value is None or not value.strip():
        raise ValueError("empty value")
    number = kind(value.strip())
    if kind is float and not math.isfinite(number):
        raise ValueError("value is not finite")
    return number

def _as_tags(value) -> List[str]:
    """Return value as a de-duplicated list of lowercase, stripped tags.

    Accepts a comma-separated string or a list/tuple/set of strings. Blank items
    are dropped and anything else gives []. Sets are sorted so the order is stable.
    """
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (set, frozenset)):
        items = sorted(value, key=str)
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        return []
    tags: List[str] = []
    for item in items:
        tag = _norm(item)
        if tag and tag not in tags:
            tags.append(tag)
    return tags

def load_songs(csv_path: str) -> List[Dict]:
    """Load songs.csv into a list of dicts, converting numeric columns to int/float.

    Required by src/main.py

    Returns:
        list[dict[str, str | int | float | list[str] | None]]: one dict per song,
        keyed by the CSV column names. energy, tempo_bpm, valence, danceability
        and acousticness are floats. id (and duration_sec, year when present) are
        ints. popularity and release_decade are ints, instrumentalness and
        speechiness are floats, and detailed_mood_tags is a list of lowercase
        tags (all only when the CSV has the column); a blank cell gives None, or
        [] for the tags. Every other column (title, artist, genre, mood, ...) is
        a string.

    Rows where a required numeric field is missing or can't be converted are
    skipped with a logged warning instead of raising. If the header lacks a
    required column, a warning is logged and an empty list is returned. A
    missing file still raises FileNotFoundError.
    """
    songs: List[Dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            logger.warning("%s is missing required column(s) %s; no songs loaded", csv_path, missing)
            return songs

        for row in reader:
            # DictReader files extra, unnamed cells under the key None; ignore them.
            song = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k is not None}
            try:
                for col in FLOAT_COLUMNS:
                    song[col] = _to_number(song.get(col), float)
                for col in INT_COLUMNS:
                    if col in song:
                        song[col] = _to_number(song[col], int)
                for col in OPTIONAL_INT_COLUMNS + OPTIONAL_FLOAT_COLUMNS:
                    if col in song:
                        kind = int if col in OPTIONAL_INT_COLUMNS else float
                        song[col] = _to_number(song[col], kind) if song[col] else None
                if TAGS_COLUMN in song:
                    song[TAGS_COLUMN] = _as_tags(song[TAGS_COLUMN])
            except ValueError as err:
                logger.warning("Skipping %s line %d (%s): %r", csv_path, reader.line_num, err, row)
                continue
            songs.append(song)
    return songs

WEIGHTS = {
    "genre": 1.0,
    "mood": 1.0,
    "energy": 4.0,
    "valence": 1.0,
    "danceability": 1.0,
    "acousticness": 0.5,
    "instrumentalness": 1.0,
    "speechiness": 0.5,
    "popularity": 0.5,
    "release_decade": 0.5,
    "tag_match": 0.25,  # per overlapping detailed_mood_tags tag, not a one-off total
}
# Scored in this order, after genre and mood.
_NUMERIC_FEATURES = ("energy", "valence", "danceability", "acousticness",
                     "instrumentalness", "speechiness")
POPULARITY_SCALE = 100.0  # popularity runs 0-100, so closeness is 1 - |diff| / 100

def _norm(value) -> str:
    """Strip and lowercase a text value; None becomes ''."""
    return "" if value is None else str(value).strip().lower()

def _as_float(value) -> Optional[float]:
    """Return value as a finite float, or None if it is missing or unusable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None

def _closeness(song_val: float, target_val: float, scale: float = 1.0) -> float:
    """1.0 when identical, 0.0 when `scale` or more apart, linear in between."""
    return max(0.0, min(1.0, 1.0 - abs(float(song_val) - float(target_val)) / scale))

def _score_with_weights(user_prefs: dict, song: dict, weights: Dict[str, float]) -> tuple[float, list[str]]:
    """The scoring rules, written once. Every strategy supplies its own `weights`.

    See score_song for the rules. `weights` must have every key of WEIGHTS.
    """
    score = 0.0
    reasons: list[str] = []

    for field in ("genre", "mood"):
        pref, have = _norm(user_prefs.get(field)), _norm(song.get(field))
        if pref and have and pref == have:
            pts = weights[field]
            score += pts
            reasons.append(f"{field} match: {str(song[field]).strip()!r} (+{pts:.2f})")

    for field in _NUMERIC_FEATURES:
        target, actual = _as_float(user_prefs.get(field)), _as_float(song.get(field))
        if target is None or actual is None:
            continue
        pts = weights[field] * _closeness(actual, target)
        if pts > 0:
            score += pts
            reasons.append(f"{field} {actual:.2f} vs target {target:.2f} (+{pts:.2f})")

    target, actual = _as_float(user_prefs.get("popularity")), _as_float(song.get("popularity"))
    if target is not None and actual is not None:
        pts = weights["popularity"] * _closeness(actual, target, POPULARITY_SCALE)
        if pts > 0:
            score += pts
            reasons.append(f"popularity {actual:g} vs target {target:g} (+{pts:.2f})")

    target, actual = _as_float(user_prefs.get("release_decade")), _as_float(song.get("release_decade"))
    if target is not None and actual is not None and target == actual:
        pts = weights["release_decade"]
        score += pts
        reasons.append(f"release decade match: {actual:g}s (+{pts:.2f})")

    wanted, have = _as_tags(user_prefs.get(TAGS_COLUMN)), _as_tags(song.get(TAGS_COLUMN))
    matched = [tag for tag in wanted if tag in have]
    if matched:
        pts = weights["tag_match"] * len(matched)
        score += pts
        reasons.append(f"tag matches: {', '.join(matched)} (+{pts:.2f})")

    return score, reasons

# --- Scoring strategies ------------------------------------------------------
# A strategy decides how (user_prefs, song) becomes (score, reasons). To try a new
# mode, add a subclass and one STRATEGIES entry; score_song and recommend_songs
# never change.

class ScoringStrategy(ABC):
    """Interface every scoring mode implements."""

    @abstractmethod
    def score(self, user_prefs: dict, song: dict) -> tuple[float, list[str]]:
        """Return (score, reasons) for one song, in the same shape as score_song."""

class WeightedScoringStrategy(ScoringStrategy):
    """Scores with WEIGHTS, with `overrides` laid on top. No overrides = WEIGHTS as is.

    Subclasses normally only set `overrides`. Treat it as read-only.
    """
    overrides: Dict[str, float] = {}

    def weights(self) -> Dict[str, float]:
        return {**WEIGHTS, **self.overrides}  # built per call, so edits to WEIGHTS still apply

    def score(self, user_prefs: dict, song: dict) -> tuple[float, list[str]]:
        return _score_with_weights(user_prefs, song, self.weights())

class GenreFirstStrategy(WeightedScoringStrategy):
    """Genre decides: a genre match is worth three times a mood match."""
    overrides = {"genre": 3.0, "mood": 1.0, "energy": 1.0}

class MoodFirstStrategy(WeightedScoringStrategy):
    """Mood decides: a mood match is worth three times a genre match."""
    overrides = {"genre": 1.0, "mood": 3.0, "energy": 1.0}

class EnergyFocusedStrategy(WeightedScoringStrategy):
    """Energy closeness decides: it is worth four times a genre or mood match."""
    overrides = {"genre": 1.0, "mood": 1.0, "energy": 4.0}

STRATEGIES: Dict[str, ScoringStrategy] = {
    "genre_first": GenreFirstStrategy(),
    "mood_first": MoodFirstStrategy(),
    "energy_focused": EnergyFocusedStrategy(),
}
# What score_song uses when no mode is given: WEIGHTS exactly as written above.
# (Today that happens to equal energy_focused.)
DEFAULT_STRATEGY: ScoringStrategy = WeightedScoringStrategy()

def get_strategy(mode=None) -> ScoringStrategy:
    """Resolve None, a mode name, or a ScoringStrategy to a strategy.

    Names ignore case and treat '-' or spaces like '_'. An unknown name raises
    ValueError instead of quietly falling back, so a typo can't change results unseen.
    """
    if mode is None:
        return DEFAULT_STRATEGY
    if isinstance(mode, ScoringStrategy):
        return mode
    key = _norm(mode).replace("-", "_").replace(" ", "_")
    try:
        return STRATEGIES[key]
    except KeyError:
        raise ValueError(f"unknown scoring mode {mode!r}; choose from {', '.join(STRATEGIES)}") from None

def score_song(user_prefs: dict, song: dict, mode=None) -> tuple[float, list[str]]:
    """Score one song against user preferences and explain which rules earned points.

    Required by recommend_songs() and src/main.py

    `mode` picks the scoring strategy: None (WEIGHTS as written), a name in
    STRATEGIES ("genre_first", "mood_first", "energy_focused"), or a
    ScoringStrategy object. The scoring itself is delegated to that strategy.

    Returns:
        tuple[float, list[str]]: (score, reasons). reasons holds one short
        string per rule that awarded points, in scoring order, such as
        "genre match: 'pop' (+1.00)". Only the preferences the user gave can
        earn points, so the maximum is the sum of the weights for those
        preferences. With the default WEIGHTS that is 8.5 for genre, mood,
        energy, valence, danceability and acousticness together, plus
        1.0 + 0.5 + 0.5 + 0.5 for instrumentalness, speechiness, popularity and
        release_decade, plus 0.25 for each tag the user lists.

    Rules (weights from the strategy): genre and mood are case-insensitive,
    whitespace-stripped exact matches. Each numeric feature earns
    weight * (1 - |song - target|), clamped to [0, 1], and only when both
    user_prefs and song have a usable value for it. Popularity uses the same
    formula on a 0-100 scale. release_decade earns its weight only on an exact
    match. detailed_mood_tags (a list, or a comma-separated string) earns the
    "tag_match" weight for each tag the song shares with the user. Missing or
    unusable values are skipped, never raised. Pure function: nothing is mutated
    or printed.
    """
    return get_strategy(mode).score(user_prefs, song)

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5, mode=None) -> List[Tuple[Dict, float, str]]:
    """Score every song with the chosen `mode` and return the top k as (song, score, explanation), best first."""
    strategy = get_strategy(mode)  # resolved once, so a bad mode fails before any scoring
    scored = ((song, *strategy.score(user_prefs, song)) for song in songs)  # (song, score, reasons)
    # Highest score first; ties broken alphabetically by title so results are repeatable.
    ranked = sorted(scored, key=lambda r: (-r[1], str(r[0].get("title", "")).lower()))
    return [
        (song, score, "; ".join(reasons) or "no matching features")
        for song, score, reasons in ranked[:max(k, 0)]
    ]

ARTIST_DUPLICATE_PENALTY = 1.5
GENRE_DUPLICATE_PENALTY = 1.0

def get_top_recommendations(
    user_prefs: Dict,
    songs: List[Dict],
    n: int = 5,
    mode="genre_first",
    *,
    artist_penalty: float = ARTIST_DUPLICATE_PENALTY,
    genre_penalty: float = GENRE_DUPLICATE_PENALTY,
) -> List[Tuple[Dict, float, str]]:
    """Pick the top n songs greedily, penalizing repeats of an artist or genre already picked.

    Each song gets its base score from the `mode` strategy (same as score_song).
    Then n times: take the best remaining song, add it to the result, and note its
    artist and genre. A remaining song whose artist is already picked loses
    `artist_penalty`, and one whose genre is already picked loses `genre_penalty`.
    Each penalty applies once however many earlier picks share the artist or genre
    (it is a yes/no test against the picked sets, not a running total).

    Returns the same (song, score, explanation) tuples as recommend_songs, in pick
    order. A penalized pick carries its adjusted score, which can drop below zero,
    plus reasons such as "diversity penalty (artist duplicate): -1.50". Artist and
    genre compare like score_song does (case and edge spaces ignored); a blank one
    is never a duplicate. Set both penalties to 0 to get plain recommend_songs order.
    """
    if artist_penalty < 0 or genre_penalty < 0:
        raise ValueError("penalties must be 0 or more")
    strategy = get_strategy(mode)  # resolved first, so a bad mode fails before any scoring
    pool = [(song, *strategy.score(user_prefs, song)) for song in songs]  # (song, base score, reasons)
    picked: List[Tuple[Dict, float, str]] = []
    seen_artists: set = set()
    seen_genres: set = set()

    def penalties(song: Dict) -> List[Tuple[str, float]]:
        found = []
        if artist_penalty > 0 and _norm(song.get("artist")) in seen_artists:
            found.append(("artist", artist_penalty))
        if genre_penalty > 0 and _norm(song.get("genre")) in seen_genres:
            found.append(("genre", genre_penalty))
        return found

    def rank(item) -> Tuple[float, str]:
        song, base, _ = item
        return (-(base - sum(cost for _, cost in penalties(song))), str(song.get("title", "")).lower())

    while pool and len(picked) < n:
        song, base, reasons = pool.pop(min(range(len(pool)), key=lambda i: rank(pool[i])))
        applied = penalties(song)
        reasons = reasons + [f"diversity penalty ({kind} duplicate): -{cost:.2f}" for kind, cost in applied]
        picked.append((song, base - sum(cost for _, cost in applied), "; ".join(reasons) or "no matching features"))
        # Blank artist/genre are never recorded, so two unknowns are not treated as a repeat.
        seen_artists.add(_norm(song.get("artist")))
        seen_genres.add(_norm(song.get("genre")))
        seen_artists.discard("")
        seen_genres.discard("")
    return picked
