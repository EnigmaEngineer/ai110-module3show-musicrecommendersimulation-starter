# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

**VibeFinder 1.0** is a content-based recommender for a 10-song catalog. A listener's taste profile (favorite genre and mood, plus optional targets for energy, valence, danceability and more) is compared with every song. Each song earns points for matching labels and for numbers that are *close* to the target, and the top 5 are shown in a table with the reason for every point. The project includes three scoring modes (Genre-First, Mood-First, Energy-Focused), five extra song features, and a diversity penalty that discourages repeating an artist or genre. It also documents where the system helps and where it misleads: see `model_card.md`.

---

## How The System Works

### How real-world recommendations work

Platforms like Spotify and YouTube combine two ideas. **Collaborative filtering** learns from the behavior of millions of users (likes, skips, playlist adds, watch time) and recommends what similar listeners enjoyed. **Content-based filtering** looks at the attributes of the songs themselves (genre, mood, tempo, energy) and recommends items that resemble what a user already likes. Real systems blend both and train on huge amounts of behavior data.

My version is purely **content-based**. It has no other users and no listening history, so it cannot learn from crowds. Instead it prioritizes **closeness to a stated taste**: it rewards songs whose numeric features (energy above all) are *near* the user's targets, not simply higher or lower, and it gives points for a matching genre and mood.

### Features

**Each song** (a row of `data/songs.csv`) has `id`, `title`, `artist`, `genre`, `mood`, `energy`, `tempo_bpm`, `valence`, `danceability` and `acousticness`, plus five optional columns: `popularity` (0-100), `release_decade`, `detailed_mood_tags` (comma-separated), `instrumentalness` and `speechiness` (0-1). So far only two songs have the optional columns filled in.

- **Scored:** `genre`, `mood`, `energy`, `valence`, `danceability`, `acousticness`, and the five optional columns whenever both the song and the profile have a value.
- **Not scored:** `id`, `title`, `tempo_bpm` (loaded but unused). `artist` is not scored either, but the diversity penalty uses it.

**A taste profile** is a dictionary. Any key can be left out and is then ignored: `genre`, `mood`, `energy`, `valence`, `danceability`, `acousticness`, `instrumentalness`, `speechiness`, `popularity`, `release_decade`, `detailed_mood_tags` (a list or a comma-separated string).

### Data flow

```
Input                     Process                                           Output
-----                     -------                                           ------
User prefs (dict)  --->   load_songs("data/songs.csv")
                          score_song(user_prefs, song, mode)
                            -> (score, reasons) for every song
                          get_top_recommendations: take the best song,
                            then subtract 1.5 (same artist) / 1.0 (same
                            genre) from the remaining songs, repeat    --->   Top 5 as a table
                          (ties: alphabetical by title)                       Rank, Title, Artist,
                                                                              Score, Reasons
```

### Algorithm Recipe

**Scoring rule (one song).** Only the preferences the listener gives can earn points. Default weights:

| Component | Points | How it is earned |
|---|---|---|
| Genre | 1.0 | exact match (case and edge spaces ignored) |
| Mood | 1.0 | exact match |
| Energy | up to 4.0 | `weight x (1 - abs(song - target))`, never below 0 |
| Valence | up to 1.0 | same closeness rule |
| Danceability | up to 1.0 | same closeness rule |
| Acousticness | up to 0.5 | same closeness rule |
| Instrumentalness | up to 1.0 | same closeness rule |
| Speechiness | up to 0.5 | same closeness rule |
| Popularity | up to 0.5 | closeness on a 0-100 scale: `1 - abs(diff) / 100` |
| Release decade | 0.5 | exact match |
| Mood tags | 0.25 per tag | each tag the song shares with the profile |

With the first six rows filled in the most a song can score is **8.5**. All ten features give 11.0, plus 0.25 for each tag listed. The closeness rule rewards songs *near* the target, not simply higher or lower: an exact match earns the full weight and a song 1.0 away earns nothing.

**Scoring modes** (`--mode`). Each mode only changes three weights; everything else stays as in the table.

| Mode | Genre | Mood | Energy |
|---|---|---|---|
| `genre_first` | 3.0 | 1.0 | 1.0 |
| `mood_first` | 1.0 | 3.0 | 1.0 |
| `energy_focused` | 1.0 | 1.0 | 4.0 (the same as the default weights) |

They are built with the Strategy pattern (`ScoringStrategy` in `src/recommender.py`), so a new mode is one small class plus one dictionary entry.

**Ranking rule (all songs).**

1. Score every song against the profile.
2. Pick the best song and add it to the results.
3. Subtract 1.5 from remaining songs by an artist already picked and 1.0 from remaining songs in a genre already picked (each penalty applies once). Penalized picks show a reason such as `diversity penalty (artist duplicate): -1.50`.
4. Repeat until five songs are chosen. Ties break alphabetically by title.

`--no-diversity` skips steps 2-3 and shows the plain top 5.

**Original plan vs. what I built.** My first design used Gaussian closeness curves with narrow tolerances, partial credit from small tables of related genres and moods, and a 10-point scale. I implemented the simpler linear closeness and exact label matching described above. Related-genre credit is listed as future work in the model card.

### Expected biases and limitations

- **Energy dominates.** With the default weights energy is 4.0 of 8.5 points (47%), while genre and mood together are 2.0 (24%). A song with the right energy can beat one with the right labels.
- **The catalog is small and skewed.** Of 10 songs, 3 are lofi and 3 are chill, and 5 of the 7 genres have a single song. There are no songs with energy between 0.43 and 0.74, so a mid-energy listener has no close match.
- **Correlated features count the same thing several times.** Energy tracks acousticness (r = -0.99), tempo (0.96) and danceability (0.86) across the catalog, so a listener who wants high energy *and* an acoustic sound cannot be satisfied.
- **Labels are exact.** "indie pop" earns nothing for a "pop" listener, and "chill" and "relaxed" count as unrelated.
- **Diversity has limits.** With 10 songs the penalty cannot always remove a repeated artist, and it can demote songs in the listener's own favorite genre.
- **One genre, one mood and no history.** The profile cannot describe someone with several tastes.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app from the project root:

   ```bash
   python -m src.main
   ```

   Options:

   ```bash
   python -m src.main --mode mood-first     # genre_first, mood_first or energy_focused
   python -m src.main --no-diversity        # plain top 5, no artist/genre penalty
   ```

### Running Tests

```bash
pytest
```

The tests cover the starter checks (`tests/test_recommender.py`), edge cases and adversarial profiles (`tests/test_scoring_edge_cases.py`), the new song features, the scoring modes, the diversity penalty, and the table output. 439 pass; 6 more are marked as expected failures because they record known problems in the scoring code (see the model card).

---

## Sample Recommendation Output

Output of `python -m src.main` on the 10-song catalog, one block per profile (top 5 each, pasted verbatim from the terminal, with the diversity penalty on). Add `--no-diversity` to see the plain ranking.

### High-Energy Pop

```
Profile: High-Energy Pop
  genre=pop | mood=happy | energy=0.9 | valence=0.8 | danceability=0.85 | acousticness=0.1

TOP 5 RECOMMENDATIONS
+--------+------------------+---------------+---------+---------------------------------------------+
|   Rank | Title            | Artist        |   Score | Reasons                                     |
+========+==================+===============+=========+=============================================+
|      1 | Sunrise City     | Neon Echo     |    8.04 | genre match: 'pop' (+1.00)                  |
|        |                  |               |         | mood match: 'happy' (+1.00)                 |
|        |                  |               |         | energy 0.82 vs target 0.90 (+3.68)          |
|        |                  |               |         | valence 0.84 vs target 0.80 (+0.96)         |
|        |                  |               |         | danceability 0.79 vs target 0.85 (+0.94)    |
|        |                  |               |         | acousticness 0.18 vs target 0.10 (+0.46)    |
+--------+------------------+---------------+---------+---------------------------------------------+
|      2 | Rooftop Lights   | Indigo Parade |    6.77 | mood match: 'happy' (+1.00)                 |
|        |                  |               |         | energy 0.76 vs target 0.90 (+3.44)          |
|        |                  |               |         | valence 0.81 vs target 0.80 (+0.99)         |
|        |                  |               |         | danceability 0.82 vs target 0.85 (+0.97)    |
|        |                  |               |         | acousticness 0.35 vs target 0.10 (+0.38)    |
+--------+------------------+---------------+---------+---------------------------------------------+
|      3 | Gym Hero         | Max Pulse     |    6.29 | genre match: 'pop' (+1.00)                  |
|        |                  |               |         | energy 0.93 vs target 0.90 (+3.88)          |
|        |                  |               |         | valence 0.77 vs target 0.80 (+0.97)         |
|        |                  |               |         | danceability 0.88 vs target 0.85 (+0.97)    |
|        |                  |               |         | acousticness 0.05 vs target 0.10 (+0.47)    |
|        |                  |               |         | diversity penalty (genre duplicate): -1.00  |
+--------+------------------+---------------+---------+---------------------------------------------+
|      4 | Storm Runner     | Voltline      |    5.95 | energy 0.91 vs target 0.90 (+3.96)          |
|        |                  |               |         | valence 0.48 vs target 0.80 (+0.68)         |
|        |                  |               |         | danceability 0.66 vs target 0.85 (+0.81)    |
|        |                  |               |         | acousticness 0.10 vs target 0.10 (+0.50)    |
+--------+------------------+---------------+---------+---------------------------------------------+
|      5 | Night Drive Loop | Neon Echo     |    3.91 | energy 0.75 vs target 0.90 (+3.40)          |
|        |                  |               |         | valence 0.49 vs target 0.80 (+0.69)         |
|        |                  |               |         | danceability 0.73 vs target 0.85 (+0.88)    |
|        |                  |               |         | acousticness 0.22 vs target 0.10 (+0.44)    |
|        |                  |               |         | diversity penalty (artist duplicate): -1.50 |
+--------+------------------+---------------+---------+---------------------------------------------+
```

### Chill Lofi

```
Profile: Chill Lofi
  genre=lofi | mood=chill | energy=0.38 | valence=0.58 | danceability=0.58 | acousticness=0.8

TOP 5 RECOMMENDATIONS
+--------+---------------------+----------------+---------+---------------------------------------------+
|   Rank | Title               | Artist         |   Score | Reasons                                     |
+========+=====================+================+=========+=============================================+
|      1 | Library Rain        | Paper Lanterns |    8.33 | genre match: 'lofi' (+1.00)                 |
|        |                     |                |         | mood match: 'chill' (+1.00)                 |
|        |                     |                |         | energy 0.35 vs target 0.38 (+3.88)          |
|        |                     |                |         | valence 0.60 vs target 0.58 (+0.98)         |
|        |                     |                |         | danceability 0.58 vs target 0.58 (+1.00)    |
|        |                     |                |         | acousticness 0.86 vs target 0.80 (+0.47)    |
+--------+---------------------+----------------+---------+---------------------------------------------+
|      2 | Midnight Coding     | LoRoom         |    7.23 | genre match: 'lofi' (+1.00)                 |
|        |                     |                |         | mood match: 'chill' (+1.00)                 |
|        |                     |                |         | energy 0.42 vs target 0.38 (+3.84)          |
|        |                     |                |         | valence 0.56 vs target 0.58 (+0.98)         |
|        |                     |                |         | danceability 0.62 vs target 0.58 (+0.96)    |
|        |                     |                |         | acousticness 0.71 vs target 0.80 (+0.45)    |
|        |                     |                |         | diversity penalty (genre duplicate): -1.00  |
+--------+---------------------+----------------+---------+---------------------------------------------+
|      3 | Spacewalk Thoughts  | Orbit Bloom    |    6.80 | mood match: 'chill' (+1.00)                 |
|        |                     |                |         | energy 0.28 vs target 0.38 (+3.60)          |
|        |                     |                |         | valence 0.65 vs target 0.58 (+0.93)         |
|        |                     |                |         | danceability 0.41 vs target 0.58 (+0.83)    |
|        |                     |                |         | acousticness 0.92 vs target 0.80 (+0.44)    |
+--------+---------------------+----------------+---------+---------------------------------------------+
|      4 | Coffee Shop Stories | Slow Stereo    |    6.25 | energy 0.37 vs target 0.38 (+3.96)          |
|        |                     |                |         | valence 0.71 vs target 0.58 (+0.87)         |
|        |                     |                |         | danceability 0.54 vs target 0.58 (+0.96)    |
|        |                     |                |         | acousticness 0.89 vs target 0.80 (+0.46)    |
+--------+---------------------+----------------+---------+---------------------------------------------+
|      5 | Focus Flow          | LoRoom         |    4.88 | genre match: 'lofi' (+1.00)                 |
|        |                     |                |         | energy 0.40 vs target 0.38 (+3.92)          |
|        |                     |                |         | valence 0.59 vs target 0.58 (+0.99)         |
|        |                     |                |         | danceability 0.60 vs target 0.58 (+0.98)    |
|        |                     |                |         | acousticness 0.78 vs target 0.80 (+0.49)    |
|        |                     |                |         | diversity penalty (artist duplicate): -1.50 |
|        |                     |                |         | diversity penalty (genre duplicate): -1.00  |
+--------+---------------------+----------------+---------+---------------------------------------------+
```

### Deep Intense Rock

```
Profile: Deep Intense Rock
  genre=rock | mood=intense | energy=0.92 | valence=0.45 | danceability=0.65 | acousticness=0.08

TOP 5 RECOMMENDATIONS
+--------+------------------+---------------+---------+------------------------------------------+
|   Rank | Title            | Artist        |   Score | Reasons                                  |
+========+==================+===============+=========+==========================================+
|      1 | Storm Runner     | Voltline      |    8.41 | genre match: 'rock' (+1.00)              |
|        |                  |               |         | mood match: 'intense' (+1.00)            |
|        |                  |               |         | energy 0.91 vs target 0.92 (+3.96)       |
|        |                  |               |         | valence 0.48 vs target 0.45 (+0.97)      |
|        |                  |               |         | danceability 0.66 vs target 0.65 (+0.99) |
|        |                  |               |         | acousticness 0.10 vs target 0.08 (+0.49) |
+--------+------------------+---------------+---------+------------------------------------------+
|      2 | Gym Hero         | Max Pulse     |    6.90 | mood match: 'intense' (+1.00)            |
|        |                  |               |         | energy 0.93 vs target 0.92 (+3.96)       |
|        |                  |               |         | valence 0.77 vs target 0.45 (+0.68)      |
|        |                  |               |         | danceability 0.88 vs target 0.65 (+0.77) |
|        |                  |               |         | acousticness 0.05 vs target 0.08 (+0.48) |
+--------+------------------+---------------+---------+------------------------------------------+
|      3 | Night Drive Loop | Neon Echo     |    5.63 | energy 0.75 vs target 0.92 (+3.32)       |
|        |                  |               |         | valence 0.49 vs target 0.45 (+0.96)      |
|        |                  |               |         | danceability 0.73 vs target 0.65 (+0.92) |
|        |                  |               |         | acousticness 0.22 vs target 0.08 (+0.43) |
+--------+------------------+---------------+---------+------------------------------------------+
|      4 | Rooftop Lights   | Indigo Parade |    5.20 | energy 0.76 vs target 0.92 (+3.36)       |
|        |                  |               |         | valence 0.81 vs target 0.45 (+0.64)      |
|        |                  |               |         | danceability 0.82 vs target 0.65 (+0.83) |
|        |                  |               |         | acousticness 0.35 vs target 0.08 (+0.36) |
+--------+------------------+---------------+---------+------------------------------------------+
|      5 | Midnight Coding  | LoRoom        |    4.04 | energy 0.42 vs target 0.92 (+2.00)       |
|        |                  |               |         | valence 0.56 vs target 0.45 (+0.89)      |
|        |                  |               |         | danceability 0.62 vs target 0.65 (+0.97) |
|        |                  |               |         | acousticness 0.71 vs target 0.08 (+0.18) |
+--------+------------------+---------------+---------+------------------------------------------+
```

### Conflicted Listener

```
Profile: Conflicted Listener
  genre=jazz | mood=relaxed | energy=0.9 | acousticness=0.9

TOP 5 RECOMMENDATIONS
+--------+---------------------+---------------+---------+------------------------------------------+
|   Rank | Title               | Artist        |   Score | Reasons                                  |
+========+=====================+===============+=========+==========================================+
|      1 | Coffee Shop Stories | Slow Stereo   |    4.38 | genre match: 'jazz' (+1.00)              |
|        |                     |               |         | mood match: 'relaxed' (+1.00)            |
|        |                     |               |         | energy 0.37 vs target 0.90 (+1.88)       |
|        |                     |               |         | acousticness 0.89 vs target 0.90 (+0.49) |
+--------+---------------------+---------------+---------+------------------------------------------+
|      2 | Storm Runner        | Voltline      |    4.06 | energy 0.91 vs target 0.90 (+3.96)       |
|        |                     |               |         | acousticness 0.10 vs target 0.90 (+0.10) |
+--------+---------------------+---------------+---------+------------------------------------------+
|      3 | Gym Hero            | Max Pulse     |    3.96 | energy 0.93 vs target 0.90 (+3.88)       |
|        |                     |               |         | acousticness 0.05 vs target 0.90 (+0.08) |
+--------+---------------------+---------------+---------+------------------------------------------+
|      4 | Rooftop Lights      | Indigo Parade |    3.67 | energy 0.76 vs target 0.90 (+3.44)       |
|        |                     |               |         | acousticness 0.35 vs target 0.90 (+0.22) |
+--------+---------------------+---------------+---------+------------------------------------------+
|      5 | Night Drive Loop    | Neon Echo     |    3.56 | energy 0.75 vs target 0.90 (+3.40)       |
|        |                     |               |         | acousticness 0.22 vs target 0.90 (+0.16) |
+--------+---------------------+---------------+---------+------------------------------------------+
```

---

## Experiments You Tried

- **Weight shift (genre 2.0 to 1.0, energy 2.0 to 4.0).** For the High-Energy Pop profile the top 5 came out in exactly the same order; only the scores changed (Sunrise City 7.20 to 8.04) and the maximum went from 7.5 to 8.5. The experiment made the results different, not more accurate.
- **Five new song features** (popularity, release decade, detailed mood tags, instrumentalness, speechiness). Each has its own scoring rule and reason string. Only two of the ten songs have values filled in so far, so these features can only score those two.
- **Scoring modes (Strategy pattern).** `genre_first`, `mood_first` and `energy_focused`, chosen with `--mode`. For High-Energy Pop, genre-first puts Gym Hero (pop, intense) second and mood-first puts Rooftop Lights (indie pop, happy) second. `energy_focused` gives exactly the same results as the default weights.
- **Diversity penalty.** Repeating an artist costs 1.5 points and repeating a genre costs 1.0. Gym Hero dropped from 2nd to 3rd for High-Energy Pop, and Focus Flow fell from 3rd to 5th for Chill Lofi. A lofi song with energy 0.42 also entered Deep Intense Rock's top 5, which shows the cost of forcing variety.
- **Different types of users.** Four profiles (High-Energy Pop, Chill Lofi, Deep Intense Rock, Conflicted Listener), plus a listener who only gives "energy 0.58" and one whose genre is not in the catalog. Pop and Lofi share no songs at all; the mid-energy listener gets a near-tie across four genres.
- **Adversarial inputs.** 27 edge-case profiles (wrong types, out-of-range numbers, empty profiles, case and spacing tricks). They found six real problems, recorded as expected failures in `tests/test_scoring_edge_cases.py`.

---

## Limitations and Risks

- **Tiny catalog.** 10 songs, 7 genres, 6 moods. Only lofi has three songs, so most genres have a single song.
- **A hole in the middle of the energy range.** Five songs sit at 0.75 to 0.93 and five at 0.28 to 0.42, with nothing between. Those same loud songs (Sunrise City, Gym Hero, Rooftop Lights, Storm Runner, Night Drive Loop) fill most top-5 lists, and a listener who wants energy around 0.58 gets what is effectively a tie.
- **Exact-match labels.** "indie pop" earns nothing for a "pop" listener, and mood is a yes/no match, so "chill" and "relaxed" count as completely different.
- **No "nothing fits" answer.** A listener whose genre is not in the catalog still gets five songs, picked by numbers alone.
- **Diversity has limits.** With only 10 songs the penalty cannot always remove a repeated artist, and it can demote songs in the listener's own favorite genre.
- **Features not used.** Tempo is loaded but never scored, and lyrics, language and listening history are not considered.

The model card (`model_card.md`) goes deeper on all of these.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

**What I learned about how recommenders turn data into predictions.** A recommender is a scorecard: each song earns points for how well its labels and numbers match what the listener asked for, and the highest totals win. It can look smart without understanding music. Gym Hero keeps appearing for people who want happy pop because it is tagged pop, very energetic and danceable, and the system only checks whether the mood tag is the same word. The weights matter a lot, but changing them is not the same as improving the results: quadrupling the energy weight left the top 5 in the same order.

**Where bias or unfairness could show up.** The catalog decides who gets served. With half the songs loud and half quiet, mid-energy listeners get a near-tie that looks like a recommendation, and a listener whose genre is missing still gets five songs with no warning. Fixes carry trade-offs too: the diversity penalty reduces repeats but can push down a listener's favorite genre or let a poor energy match into the list. Testing with unusual profiles showed me these problems far faster than the happy-path profiles did.

