"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import argparse
import textwrap

from tabulate import tabulate

try:
    from src.recommender import STRATEGIES, get_top_recommendations, load_songs, recommend_songs  # python -m src.main
except ImportError:
    from recommender import STRATEGIES, get_top_recommendations, load_songs, recommend_songs      # python src/main.py


# Taste profiles to try. Keys are the ones score_song reads; numeric targets are
# on a 0.0 to 1.0 scale. Any numeric key can be left out and is then ignored.
PROFILES = {
    "High-Energy Pop": {
        "genre": "pop", "mood": "happy",
        "energy": 0.90, "valence": 0.80, "danceability": 0.85, "acousticness": 0.10,
    },
    "Chill Lofi": {
        "genre": "lofi", "mood": "chill",
        "energy": 0.38, "valence": 0.58, "danceability": 0.58, "acousticness": 0.80,
    },
    "Deep Intense Rock": {
        "genre": "rock", "mood": "intense",
        "energy": 0.92, "valence": 0.45, "danceability": 0.65, "acousticness": 0.08,
    },
    # Edge case: wants loud, high-energy songs that are also acoustic. The catalog
    # has none, so this shows how the scoring handles conflicting preferences.
    "Conflicted Listener": {
        "genre": "jazz", "mood": "relaxed",
        "energy": 0.90, "acousticness": 0.90,
    },
}


HEADERS = ["Rank", "Title", "Artist", "Score", "Reasons"]
REASON_WIDTH = 46  # a longer reason wraps onto an indented line instead of widening the table


def build_rows(recommendations: list) -> list:
    """One row per recommendation: [rank, title, artist, score, reasons], reasons one per line."""
    rows = []
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        reasons = "\n".join(
            textwrap.fill(reason, width=REASON_WIDTH, subsequent_indent="  ")
            for reason in explanation.split("; ")
        )
        rows.append([rank, song["title"], song.get("artist", "unknown artist"), score, reasons])
    return rows


def print_recommendations(name: str, user_prefs: dict, recommendations: list) -> None:
    """Print the profile, then its top picks as a grid table."""
    settings = " | ".join(f"{key}={value}" for key, value in user_prefs.items())
    print(f"\nProfile: {name}\n  {settings}\n")

    if not recommendations:
        print(" No songs to recommend.\n")
        return

    print(f"TOP {len(recommendations)} RECOMMENDATIONS")
    print(tabulate(
        build_rows(recommendations),
        headers=HEADERS,
        tablefmt="grid",  # plain ASCII; fancy_grid draws box characters some Windows consoles can't print
        floatfmt=".2f",
        colalign=("right", "left", "left", "right", "left"),
    ))


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Music Recommender Simulation")
    parser.add_argument(
        "--mode",
        type=lambda text: text.strip().lower().replace("-", "_"),  # mood-first == mood_first
        choices=sorted(STRATEGIES),
        help="scoring strategy; leave out to use the WEIGHTS in recommender.py as written",
    )
    parser.add_argument(
        "--no-diversity",
        action="store_true",
        help="skip the artist/genre diversity penalty and show the plain top 5",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")
    if args.mode:
        print(f"Scoring mode: {args.mode}")

    for name, user_prefs in PROFILES.items():
        if args.no_diversity:
            recommendations = recommend_songs(user_prefs, songs, k=5, mode=args.mode)
        else:
            recommendations = get_top_recommendations(user_prefs, songs, n=5, mode=args.mode)
        print_recommendations(name, user_prefs, recommendations)


if __name__ == "__main__":
    main()
