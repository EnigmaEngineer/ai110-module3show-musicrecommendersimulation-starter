# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Challenge 1: Advanced Song Features

### 1. Prompt used

> "I need to add 5 advanced features to the system and update the scoring logic: popularity (int, 0-100), release_decade (int), detailed_mood_tags (comma-separated string, parsed into a list), instrumentalness (float) and speechiness (float). Update data/songs.csv, update `load_songs` to parse the new fields, update `score_song` and `WEIGHTS` (popularity: closeness to the target; release decade: exact match; tags: +0.25 per overlapping tag; instrumentalness and speechiness: the standard `_closeness` formula), and make sure the reason strings capture the new points."

### 2. Summary of changes

- **`data/songs.csv`**: added `popularity, release_decade, detailed_mood_tags, instrumentalness, speechiness`. Only Sunrise City and Midnight Coding have values so far; the other 8 rows have blank cells for me to fill in.
- **`load_songs()`**:
  - `popularity` and `release_decade` parse as `int`, `instrumentalness` and `speechiness` as `float`, through new `OPTIONAL_INT_COLUMNS` / `OPTIONAL_FLOAT_COLUMNS`.
  - `detailed_mood_tags` becomes a list through a new `_as_tags()` helper (split on commas, strip, lowercase, drop blanks and duplicates), e.g. `"nostalgic, Chill"` -> `['nostalgic', 'chill']`.
  - A blank cell means "unknown": the value is `None` (or `[]` for tags) and the row is kept. A non-blank value that cannot be parsed skips the row, like the required columns. A CSV without the new columns still loads.
- **`WEIGHTS`**: added `instrumentalness 1.0`, `speechiness 0.5`, `popularity 0.5`, `release_decade 0.5`, and `tag_match 0.25` (per overlapping tag).
- **`_closeness()`**: gained an optional `scale` argument (default 1.0, so old behaviour is unchanged). Popularity uses `scale=100`.
- **`score_song()`**: instrumentalness and speechiness join the existing numeric loop; popularity, release decade and tags have their own blocks. New reason strings, for example `popularity 80 vs target 90 (+0.45)`, `release decade match: 1990s (+0.50)`, `tag matches: nostalgic, chill (+0.50)`.
- **Tests**: new `tests/test_advanced_features.py` (29 tests).

### 3. Verification (run in the session, with real output)

- **Parsing:** `load_songs("data/songs.csv")` returned all 10 songs. Sunrise City came back with `popularity=78` (`int`), `instrumentalness=0.02` (`float`) and `detailed_mood_tags=['euphoric', 'upbeat', 'sunny']`. A row with blank new cells came back with `None` values and `[]` tags.
- **Popularity math:** target 90 vs song 80 gave `0.5 * (1 - 10/100) = 0.45`. Target 100 vs song 80 gave `0.40`.
- **Tags:** one shared tag gave +0.25, two gave +0.50, and the reason lists them in the order the user typed them. Empty, `None` and non-text tag preferences score nothing and do not crash.
- **Whole suite:** 383 passed, 6 expected failures (the known bugs documented in `tests/test_scoring_edge_cases.py`).

### 4. Problems found and fixed along the way

- `popularity` was **already listed in `INT_COLUMNS`**, which makes a blank cell skip the whole row. With 8 blank rows that would have dropped most of the catalog, so I moved it to the optional group.
- My earlier edge-case tests assumed the maximum score was `sum(WEIGHTS.values())` and that `WEIGHTS` had 6 keys. With 5 new weights one test failed. I changed it to sum only the six original features.
- The `score_song` docstring was stale (it still said the maximum was 7.5 and showed `+2.00`). It now describes the current weights.

### 5. Known limits / still to do by hand

- Fill in the new columns for the other 8 songs. Until then the new features can only score two songs.
- The tag bonus has no cap: a user who lists 5 tags that all match earns 1.25.
- Popularity outside 0-100 is not rejected; it just earns fewer (or no) points.
- The existing `pts > 0` check can still print `(+0.00)` for a tiny closeness (a known issue recorded as an expected failure in the tests). The new features inherit it.

---

## Challenge 2: Multiple Scoring Modes

The full brainstorm, the design choices and the checks are in **Design Pattern (SF10)** below. In short:

- **Prompt used:** asked for multiple scoring modes (Genre-First, Mood-First, Energy-Focused) refactored with the Strategy pattern, plus a `--mode` flag in `main.py`.
- **Pattern chosen:** Strategy. `ScoringStrategy` is the interface; `GenreFirstStrategy` (genre 3.0), `MoodFirstStrategy` (mood 3.0) and `EnergyFocusedStrategy` (energy 4.0) only supply weights, and `STRATEGIES` maps mode names to them.
- **Branching:** the work was done on the `experiment/mood-first` branch and merged into `main` (fast-forward).
- **Checked:** `python -m src.main --mode mood-first` shows `mood match: 'happy' (+3.00)`; `--mode energy_focused` gives the same output as no flag; an invalid mode exits with the list of valid choices; 409 tests pass.

---

## Challenge 3: Diversity and Fairness Logic

### 1. Prompt used

> "My recommender currently scores every song and just picks the top 5. This results in the same artist or the same genre dominating the whole list. I want to implement a Diversity Penalty. Please add `get_top_recommendations(user_prefs, songs, n=5, mode="genre_first")` to recommender.py and update main.py to use it. Greedy selection: score every song, pick the best, add it to the results, then subtract 1.5 from remaining songs by an artist already picked and 1.0 from remaining songs in a genre already picked. When a song is penalized, add a reason like `diversity penalty (artist duplicate): -1.50`."

### 2. Summary of changes

- **`get_top_recommendations()`** in `src/recommender.py`, plus constants `ARTIST_DUPLICATE_PENALTY = 1.5` and `GENRE_DUPLICATE_PENALTY = 1.0`.
  - Base scores come from the chosen scoring mode (same strategies as `score_song`).
  - It then loops `n` times: take the best remaining song, move it to the results, and record its artist and genre in two sets.
  - A remaining song whose artist is in the artist set loses 1.5; one whose genre is in the genre set loses 1.0. Both can apply.
  - A penalized pick gets reasons such as `diversity penalty (artist duplicate): -1.50` and `diversity penalty (genre duplicate): -1.00`, and its score shows the adjusted value.
  - Optional keyword arguments `artist_penalty` and `genre_penalty` allow tuning. Setting both to 0 reproduces the plain `recommend_songs` order, which is how I check the new code against the old.
- **`src/main.py`** calls `get_top_recommendations` by default. A new `--no-diversity` flag switches back to the plain top 5, so I can compare both.
- **`README.md`**: the sample output is regenerated from the current default run (it also still showed the scores from before the weight experiment).
- **`tests/test_diversity.py`**: 21 new tests.

### 3. A decision I had to make

"Subtract after every pick" can be read two ways. Applied literally, a third song by an artist already picked twice would lose 1.5 twice (once per earlier pick), so penalties would grow with each repeat. Because the prompt describes a **set** of selected artists and genres, I implemented a yes/no check against the sets: each penalty applies **once**, however many earlier picks share the artist or genre. `test_penalty_applies_once_not_per_earlier_pick` records this.

### 4. How the penalty limits one artist taking the whole top 5

Each time an artist is picked, that artist's remaining songs start 1.5 points behind (and 2.5 if the genre also repeats), so a second song by the same artist only makes the list if it leads every fresh candidate by more than the penalty. It is a **nudge, not a quota**: if one artist's songs lead by more than 1.5, they can still fill the list (`test_penalty_is_a_nudge_not_a_quota` shows this on purpose).

### 5. How to verify it works

1. `python -m pytest tests/test_diversity.py -q` (21 tests).
2. Run `python src/main.py --no-diversity`, then `python src/main.py`, and compare the top 5 for each profile. Penalized songs show their `diversity penalty (...)` lines.
3. Check the zero-penalty equivalence:
   `get_top_recommendations(prefs, songs, 5, mode, artist_penalty=0, genre_penalty=0)` must equal `recommend_songs(prefs, songs, 5, mode)`.

### 6. What I observed (real output, default scoring weights)

- **High-Energy Pop:** Gym Hero (pop, same genre as the already-picked Sunrise City) goes from 7.29 to 6.29 with `diversity penalty (genre duplicate): -1.00` and drops from #2 to #3, behind Rooftop Lights (6.77).
- **Chill Lofi:** Focus Flow (LoRoom, lofi) goes from 7.38 to 4.88 (-1.50 for the repeated artist, -1.00 for the repeated genre) and drops from #3 to #5.
- **Deep Intense Rock:** the repeated Neon Echo song (Sunrise City) is pushed out, which looks good, but Midnight Coding (a lofi song with energy 0.42 for a 0.92 target) takes its place at #5 with 4.04. Variety was bought at the cost of a weak match.
- **Conflicted Listener:** Sunrise City is replaced by Night Drive Loop at #5.

### 7. Limits I found (things the earlier draft of this log got wrong)

- **A repeated artist can still appear.** The catalog has only 10 songs and just two artists with two songs each (Neon Echo, LoRoom). In High-Energy Pop, Night Drive Loop (Neon Echo) is penalized by 1.50 but stays #5; in Chill Lofi, Focus Flow (LoRoom) stays in the top 5. With only 10 songs there are too few alternatives to push them out.
- **"Max Pulse dominating" cannot happen here**, since Max Pulse has one song. Gym Hero's penalty is a *genre* penalty (both it and Sunrise City are pop), not an artist penalty.
- **Fairness trade-off:** the genre penalty hits a listener's own favorite genre. A lofi fan loses ground on Focus Flow even though lofi is exactly what they asked for. Variety is being preferred to exact-match purity.
- **Scores can go negative:** a heavily penalized song with a low base score can end below zero. I left this visible instead of clamping it, because clamping would hide the penalty.

---

## Challenge 4: Visual Summary Table

### 1. Prompt used

> "My main.py currently prints out a messy, long list for the top recommendations. I want to replace this with a clean, formatted ASCII table using the `tabulate` library. Extract the top 5 recommendations and build a list of lists with the columns Rank, Title, Artist, Score and Reasons. The Reasons column must hold the full list of reasons, joined with a comma and space or a newline so it fits inside the table. Print it with `tabulate(..., tablefmt='grid')`."

### 2. Summary of changes

- **`src/main.py`**
  - `from tabulate import tabulate`.
  - New `build_rows()` returns one `[rank, title, artist, score, reasons]` list per recommendation. Each reason goes on its own line (joined with `"\n"`), so the cell reads like a short list and the table stays narrow.
  - A reason longer than `REASON_WIDTH` (46 characters) wraps onto an indented line instead of widening the whole table.
  - `print_recommendations()` prints the profile line, then the table using `tablefmt="grid"`, `floatfmt=".2f"` and explicit column alignment (score right-aligned, text left-aligned).
  - The rows come from `get_top_recommendations` (Challenge 3), or from `recommend_songs` with `--no-diversity`, so the table shows the diversity-penalty reasons too.
- **`requirements.txt`**: added `tabulate`. It was already installed in my environment (version 0.10.0), but it was missing from the file, so a fresh install would have failed.
- **`README.md`**: sample output regenerated from the new table output.
- **`tests/test_main_table.py`**: 9 new tests.

### 3. Notes on the prompt

- `headers='keys'` only works when the rows are dictionaries (or a dataframe). With the list of lists the prompt asks for, I pass an explicit `HEADERS` list instead.
- I used `grid` rather than `fancy_grid`. `grid` is plain ASCII, while `fancy_grid` draws box characters that some Windows consoles cannot print.
- Passing real floats with `floatfmt=".2f"` keeps scores like 7.20 from being shown as 7.2.

### 4. How I verified the table formatting

- **Ran it:** `python src/main.py` printed four tables, one per profile, with the five columns and the full reasons list visible in each cell.
- **Alignment:** a test checks that every border and row line within a table has exactly the same width.
- **Row count and headers:** each profile shows five numbered rows, and all five headers appear.
- **Plain ASCII, no list repr:** the whole output passes `str.isascii()` and contains no `['...']` Python-list text.
- **One reason per line:** a test confirms `genre match: 'pop' (+1.00)` and `mood match: 'happy'` sit on consecutive lines of the same cell.
- **Long reasons:** a test builds a 20-tag reason and checks that no line exceeds `REASON_WIDTH`.
- **Score format:** a score of 7.2 prints as `7.20`.
- **Empty cases:** an empty recommendation list prints "No songs to recommend" and no table.

### 5. An edge case that did not need a fix

A song with no matching features is not a blank cell: `recommend_songs` and `get_top_recommendations` already label it `no matching features`, so the table shows that text. `test_no_matching_reasons_gives_a_filled_cell` covers it. (The earlier draft of this log claimed a manual `"No reasons"` fix; that was not needed or made.)

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

<!-- Describe the goal you asked the agent to accomplish -->

**Prompts used:**

<!-- Paste the key prompts you gave the agent -->

**What did the agent generate or change?**

<!-- List the files edited, code generated, or commands run -->

**What did you verify or fix manually?**

<!-- Describe anything the agent got wrong or that required human review -->

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

**Strategy.** Scoring is now a family of interchangeable objects. `score_song(user_prefs, song, mode)` picks one and delegates to it.

**How did AI help you brainstorm or implement it?**

**Brainstorm.** I wanted three scoring modes (Genre-First, Mood-First, Energy-Focused) without rewriting `score_song` each time. The AI and I weighed three options:

1. **`if mode == ...` branches inside `score_song`.** Quick, but every new mode edits the function and the rules get mixed with the choices.
2. **One subclass per mode that each re-implements `score`.** This is the skeleton I was given, but it would copy the whole scoring body three times.
3. **A strategy interface where the rules live in one place and each mode only supplies weights.** This is what I chose.

Strategy fits because the three modes differ only in *how much* each feature counts, so the object that varies is small and the rest stays fixed. Adding a mode becomes "write a small class and add one dictionary entry".

**Honest trade-off.** For modes that only change numbers, a plain weights dictionary would also work. The pattern earns its place when a mode needs different *behaviour* (my test `test_new_mode_needs_no_change_to_score_song` plugs in a strategy that ranks by title length without touching `score_song`).

**Where I changed the supplied skeleton, and why:**

- Each strategy does **not** re-implement scoring. The rules live once in `_score_with_weights()`, and strategies only provide an `overrides` dictionary.
- `score_song` defaults to `mode=None` (the `WEIGHTS` exactly as written) instead of `"genre_first"`. A `genre_first` default would have silently changed every existing result and broken the existing tests. Today `energy_focused` is numerically identical to the default, which is a handy check.
- An **unknown mode raises `ValueError`** instead of quietly falling back to genre-first, so a typo cannot change results unnoticed. On the command line, `argparse` shows the valid choices.

**How does the pattern appear in your final code?**

In `src/recommender.py`:

- `ScoringStrategy` (abstract base class) defines `score(user_prefs, song)`.
- `WeightedScoringStrategy` implements it once, merging `WEIGHTS` with the subclass's `overrides`.
- `GenreFirstStrategy` (genre 3.0, mood 1.0, energy 1.0), `MoodFirstStrategy` (1.0 / 3.0 / 1.0) and `EnergyFocusedStrategy` (1.0 / 1.0 / 4.0) only set `overrides`.
- `STRATEGIES` maps `"genre_first"`, `"mood_first"` and `"energy_focused"` to instances, and `get_strategy()` resolves a name, an object, or `None`.
- `score_song(..., mode=None)` and `recommend_songs(..., mode=None)` delegate to the chosen strategy.

In `src/main.py`, `--mode` (for example `python -m src.main --mode mood-first`) is passed to `recommend_songs`.

**What I checked (run in the session):**

- All 409 tests pass (6 expected failures are the known bugs recorded earlier).
- `energy_focused` gives exactly the same top 5 and scores as the default for all four profiles.
- The mode really changes results. For High-Energy Pop, `genre_first` puts Gym Hero second (6.38) and `mood_first` puts Rooftop Lights second (6.19). That is the "why does Gym Hero keep showing up?" question from my model card, now something I can switch on and off.
- The Conflicted Listener ranks Coffee Shop Stories first in every mode, but the margin over second place is 3.87 points under `genre_first` or `mood_first` and only 0.32 under `energy_focused`.
- `--mode polka` exits with an "invalid choice" error that lists the valid modes.
