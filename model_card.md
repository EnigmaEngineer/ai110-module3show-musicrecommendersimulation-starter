# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**VibeFinder 1.0**: a small, rule-based music recommender simulation.

---

## 2. Intended Use  

**Goal.** VibeFinder suggests songs from a small catalog. The listener gives a favorite genre, a favorite mood, and optional targets for energy, valence, danceability and acousticness (for example "pop, happy, energy 0.8"). The model scores every song against those wishes and returns the top 5, with reasons.

**Assumptions about the user.** It assumes a listener can describe their taste with a few labels and numbers, that one profile is enough to capture it, and that "closest to the number I asked for" is what "liking a song" means. It has no listening history and learns nothing from other people.

**Intended use.** A classroom tool for learning how a list of numbers turns into a recommendation, and for experimenting with weights and edge cases.

**Not intended for.** A real music app, real listeners, or anything that profiles people or makes money from their taste. The catalog is 10 songs, so it is not ready for any of that.

---

## 3. How the Model Works

Think of the recommender as a judge holding a scorecard. For every song in the catalog, it checks how well the song fits what the listener asked for, adds up points, and then lists the songs from the highest total to the lowest. It does not learn from other listeners and has no listening history. It only compares each song to the preferences it is given.

**What it looks at.** Each song has a genre, a mood, and a few measurements on a scale from 0 to 1: energy (calm to intense), valence (sad to cheerful), danceability, and acousticness (electronic to acoustic). The listener's profile names a favorite genre and mood and, optionally, a target for any of those measurements. For example: "pop, happy, energy 0.8".

**How points are awarded.**

- A matching genre earns 1 point.
- A matching mood earns 1 point.
- Energy earns up to 4 points, depending on how close the song's energy is to the target.
- Valence and danceability each earn up to 1 point, and acousticness up to half a point, but only when the listener gave a target for them.
- Five optional extras are scored only when both the listener and the song have a value: instrumentalness (up to 1 point), speechiness, popularity and release decade (up to half a point each), and 0.25 points for every mood tag they share.

For the measurements, the rule is "closest to what you asked for", not "highest". A song that matches the target exactly earns the full points, a song that is further away earns fewer, and a song a full 1.0 away earns none. This means a listener who wants calm music is never handed the most intense track just because its number is big. With the first six preferences filled in, the most a song can score is 8.5 (the optional extras add up to 2.5 more, plus 0.25 per tag). (My first version gave genre 2 points and energy 2 points, for a maximum of 7.5. I changed both in the experiment described in Section 7.)

**Turning scores into recommendations.** The model scores every song, then picks five one at a time. It takes the best remaining song and, before choosing the next one, subtracts 1.5 points from remaining songs by the same artist and 1.0 from remaining songs in the same genre (alphabetical by title if two songs tie). Running with `--no-diversity` skips that penalty and returns the plain top five. Three scoring modes (`--mode genre_first`, `mood_first` or `energy_focused`) change only the genre, mood and energy weights. Each recommendation comes with plain-language reasons, such as "genre match: 'pop' (+1.00)", so you can see exactly where its points came from.

**A worked example.** For a listener who wants pop, happy, energy 0.8, the song Sunrise City is pop (+1.00), happy (+1.00), and has energy 0.82, which is very close to 0.8 (+3.92). That totals 5.92, the highest in the catalog, so it comes first.

**What changed from the starter logic.** The starter project had empty placeholders: no way to load the songs, no scoring, and no ranking. I added loading the song list from the CSV file (converting the numbers so they can be compared), the scorecard above, the sort-and-pick-the-top-five step with reasons, and a readable command-line display. The whole simulation runs from the terminal with `python -m src.main`.

**A known quirk.** Energy is worth four times a genre or mood match, so closeness on that one number often decides the order. In the High-Energy Pop profile, Gym Hero (pop, but intense) ranks second, ahead of Rooftop Lights (indie pop, and happy). The genre point Gym Hero gains and the mood point Rooftop Lights gains cancel out, so Gym Hero wins mostly because its energy is closer to the target (0.93 vs. 0.76 when the listener wanted 0.9).

---

## 4. Data  

**Size.** 10 songs in `data/songs.csv`. I did not add or remove songs, only five new columns.

**What each song has.** Title, artist, genre, mood, and numbers for energy, tempo (BPM), valence, danceability and acousticness. I added five optional columns: popularity, release decade, detailed mood tags, instrumentalness and speechiness. The scorer uses everything except title, artist and tempo (artist is used by the diversity penalty). Only Sunrise City and Midnight Coding have values in the five new columns so far, so those features can only score two songs. There is no language or lyrics column.

**Genres (7).** lofi 3, pop 2, and one each of ambient, indie pop, jazz, rock and synthwave.

**Moods (6).** chill 3, happy 2, intense 2, and one each of relaxed, moody and focused. There is no "sad" mood at all.

**Energy has a hole in the middle.** Five songs sit between 0.75 and 0.93 and five between 0.28 and 0.42. Nothing falls between 0.43 and 0.74.

**What is missing from musical taste.** Hip hop, classical, country, R&B, Latin and most other genres; vocals and language; era; and any sense of the listener's history. Two artists (Neon Echo and LoRoom) account for 4 of the 10 songs.

---

## 5. Strengths  

- **Profiles that fit the catalog get answers I agree with.** For Chill Lofi the top two are Library Rain and Midnight Coding, both quiet, acoustic lofi tracks. For Deep Intense Rock, Storm Runner is first by a clear margin (8.41 vs. 6.90).
- **The preference numbers really steer the results.** Pop and Lofi share no songs at all, and the same high-energy group reshuffles sensibly between Pop and Rock.
- **It is easy to explain.** Every recommendation lists exactly which rules earned which points, and the points add up to the score.
- **It copes with messy input.** Capital letters and stray spaces in a genre still match, and missing, blank or non-numeric preferences are skipped instead of crashing. My edge-case tests cover this.
- **Ties are broken the same way every time** (alphabetically by title), with two small exceptions that my tests record as known problems.

---

## 6. Limitations and Bias 

Where the system struggles or behaves unfairly. 

**Weakness found: the energy gap creates a high-energy filter bubble and leaves mid-energy listeners underserved.** The catalog's energy values split into two clusters with nothing in between (five songs at 0.75 to 0.93 and five at 0.28 to 0.42), and after I raised the energy weight to 4.0 (47% of the 8.5 maximum), the same five high-energy songs filled the entire top 5 for both High-Energy Pop and Deep Intense Rock and four of the five slots for Conflicted Listener. A listener who wants energy around 0.58 sits in the empty gap, so the top five (Midnight Coding, Night Drive Loop, Focus Flow, Rooftop Lights, Coffee Shop Stories) are separated by only 0.20 points (3.36 to 3.16) across four different genres, which is effectively a tie that looks like a recommendation. The scoring never signals this, because a song 0.2 away on energy still earns most of the points and the system has no way to say "nothing here fits." Genre matching is also an exact string comparison, so "indie pop" earns no credit for a "pop" listener, which compounds the problem for anyone whose taste falls outside the few labels in a 10-song catalog.

**Other limits.** Mood is an exact word match, so "chill" and "relaxed" count as completely different and the system cannot tell a slightly moody song from a very moody one. Tempo is loaded but never scored, and lyrics and language are not considered. The newer popularity, decade and tag features are filled in for only two songs. It cannot say "I have nothing for you": a listener whose genre is missing from the catalog still gets five songs. Finally, a profile with fewer preferences has a lower possible maximum score, so scores from different profiles should not be compared with each other.

---

## 7. Evaluation

### Profiles I tested

I ran four taste profiles through the recommender on the 10-song catalog (current weights: genre 1.0, mood 1.0, energy 4.0, valence 1.0, danceability 1.0, acousticness 0.5). The rankings in this section are the plain top 5, as printed by `python -m src.main --no-diversity`. The default run applies the diversity penalty, described near the end of this section:

| Profile | Asks for | Top 5 (score) |
|---|---|---|
| **High-Energy Pop** | pop, happy, very energetic, danceable, not acoustic | Sunrise City (8.04), Gym Hero (7.29), Rooftop Lights (6.77), Storm Runner (5.95), Night Drive Loop (5.41) |
| **Chill Lofi** | lofi, chill, low energy, quite acoustic | Library Rain (8.33), Midnight Coding (8.23), Focus Flow (7.38), Spacewalk Thoughts (6.80), Coffee Shop Stories (6.25) |
| **Deep Intense Rock** | rock, intense, very energetic, dark-ish, not acoustic | Storm Runner (8.41), Gym Hero (6.90), Night Drive Loop (5.63), Sunrise City (5.52), Rooftop Lights (5.20) |
| **Conflicted Listener** | jazz, relaxed, but also very energetic *and* very acoustic | Coffee Shop Stories (4.38), Storm Runner (4.06), Gym Hero (3.96), Sunrise City (3.82), Rooftop Lights (3.67) |

I also tried a few extra cases: a listener who only says "energy 0.58", a "hip hop / angry" listener whose genre is not in the catalog, and a plain "pop / happy / energy 0.8" listener. I also changed the weights (genre 2.0 to 1.0, energy 2.0 to 4.0) and re-ran everything. For correctness I wrote 445 automated tests in total. 360 of them are edge cases (wrong types, out-of-range numbers, empty profiles, case and spacing in genre names); the rest cover the new features, scoring modes, diversity penalty and table output. 439 pass, and the other 6 are known problems recorded as expected failures rather than hidden.

### What I compared, pair by pair

- **Pop vs. Lofi: completely different lists, and that is correct.** Not one song appears in both. Pop wants loud and energetic, so it gets the five high-energy songs. Lofi wants quiet, so it gets the five low-energy songs. This is the clearest sign the energy setting really steers the results.
- **Pop vs. Rock: same five songs, different order.** Both profiles want high energy, so the same group shows up. What changes is who is on top: Storm Runner jumps from 4th (pop) to 1st (rock) because it is the only rock song and its mood is "intense", while Sunrise City drops from 1st to 4th because it is cheerful and rock listeners asked for something darker. That reshuffling is what I would expect.
- **Pop vs. Conflicted Listener: mostly the same loud songs, but a surprising #1.** Sunrise City, Gym Hero, Rooftop Lights and Storm Runner appear in both. But Conflicted Listener's top pick is Coffee Shop Stories, a quiet jazz song, even though they asked for very high energy. It wins because it matches jazz and relaxed (+2.0) and is very acoustic. It loses about 2 points on energy, but no other song gets any category match. Scores are also lower overall because this listener gave the system fewer preferences to earn points on.
- **Lofi vs. Rock: opposite ends, no overlap.** One difference worth noticing: Lofi's top two are only 0.10 apart (8.33 vs 8.23) because the catalog has three lofi songs that all fit. Rock's #1 beats #2 by 1.51 because there is only one rock song. A big gap does not mean "perfect match"; it can just mean "the only one".
- **Lofi vs. Conflicted Listener: only one song in common, Coffee Shop Stories.** It is the one quiet, acoustic song that also fits a jazz listener, so it lands 5th for lofi and 1st for Conflicted. That makes sense because it sits between the two tastes.
- **Rock vs. Conflicted Listener: four of five songs overlap, and Storm Runner, Gym Hero, Sunrise City and Rooftop Lights keep the same relative order.** Both want energy around 0.9. Night Drive Loop falls out for Conflicted because Rooftop Lights is a bit more acoustic and a bit closer in energy.

### Why does "Gym Hero" keep showing up for people who just want Happy Pop?

Gym Hero is a high-energy pop workout track. The system does not understand "mood" the way a person does. It only checks whether the mood tag is *exactly* the same word, yes or no, and "intense" is not "happy", so it loses a single point out of a possible 8.5. Everything else about Gym Hero fits a happy-pop listener very well: it is tagged pop, it is extremely energetic (0.93 when the listener wanted 0.9), it is very danceable, and it is not acoustic. For the High-Energy Pop profile it scores 7.29 out of 8.5, which is 86%, and the only song ahead of it is Sunrise City, which wins by 0.75, almost entirely thanks to being tagged "happy". The catalog is also tiny: only two songs are tagged pop at all, so Gym Hero is half of the "pop" shelf. It shows up for Rock listeners too, because it is tagged "intense" and has very high energy. In short, Gym Hero is not being picked because it is happy, it is being picked because it is loud, danceable and pop, and the system cannot tell that a gym workout song feels different from a feel-good song.

### What surprised me

- **Gym Hero appears in three of the four profiles.** A few loud songs end up everywhere, which is the filter-bubble effect described in Section 6.
- **A quiet jazz song was #1 for someone who asked for very energetic music.** It shows that a tag match can outweigh a mismatch on the number the listener cared about most.
- **Making energy four times more important than genre did not change the order for the main pop profile** at all (Sunrise City, Gym Hero, Rooftop Lights, Storm Runner, Night Drive Loop stayed in the same order); only the scores changed. So that experiment made the results different in size but not more accurate.
- **A listener who only asked for "energy 0.58" got five songs from four different genres separated by just 0.20 points.** The catalog has no songs between energy 0.43 and 0.74, so for that taste the list is basically a coin flip dressed up as a recommendation.
- **A genre that is not in the catalog (hip hop) is silently ignored.** The system still returns five songs, picked by numbers alone, with no warning that nothing fit.

### What the diversity penalty changed

The default run (`python -m src.main`) subtracts 1.5 points for a repeated artist and 1.0 for a repeated genre. On the four profiles:

- **High-Energy Pop:** Gym Hero (pop, same genre as the already-picked Sunrise City) falls from 7.29 to 6.29 and drops from 2nd to 3rd, so Rooftop Lights moves up to 2nd.
- **Chill Lofi:** Focus Flow (same artist and genre as Midnight Coding) falls from 7.38 to 4.88 and drops from 3rd to 5th.
- **Deep Intense Rock:** the repeated Neon Echo song (Sunrise City) is pushed out, but Midnight Coding, a lofi song with energy 0.42 for a 0.92 target, takes its place at 5th with 4.04. Variety was bought with a weaker match.
- **Repeats can survive:** with only 10 songs, Night Drive Loop (a second Neon Echo song) still makes High-Energy Pop's top 5 even after losing 1.5 points, and Focus Flow stays in Chill Lofi's. The penalty is a nudge, not a quota.

### Do the results make sense?

For the profiles that fit the catalog well (Lofi and Rock), the top song is exactly the one I would pick by ear. For Pop the top two are reasonable, but third-place Rooftop Lights, which really is happy, loses to Gym Hero mainly on energy (0.76 vs. 0.93 when the listener wanted 0.9); Gym Hero's genre point and Rooftop Lights' mood point cancel out. The profile that did not fit the catalog (Conflicted Listener) produced the least trustworthy list, which is itself a useful finding: the recommender is only as good as the songs it has.

---

## 8. Future Work  

1. **A bigger, more varied catalog.** Go from 10 songs to at least 100, with several songs per genre and plenty of mid-energy tracks. At the very least, 3 songs for each of the 7 genres would take 21.
2. **Say so when nothing fits.** If no song is a real match (no genre, no mood, energy far away), tell the listener instead of showing a "top 5" that is really a tie.
3. **Related genres and moods.** Give partial credit when labels are close ("indie pop" is near "pop", "relaxed" is near "chill"), so one exact spelling does not decide everything. I would try this before adding a flat penalty for a genre mismatch, because a flat penalty subtracts the same amount from every off-genre song and so would not change their order.
4. **Smarter variety.** I added a simple artist and genre penalty. With only 10 songs it cannot always remove a repeat and it can lift a poor match, so next I would scale the penalty to how many good alternatives exist.
5. **Handle mixed tastes.** Let a listener hold two profiles at once (for example "gym" and "study") instead of forcing one blended set of numbers.
6. **Learn from other listeners.** Collaborative filtering would use what similar people liked, rather than only matching a song's numbers to one profile.

---

## 9. Personal Reflection  

**Biggest learning moment.** I was surprised how a plain scorecard of added-up points can produce a list that looks like a real playlist, and how quickly that list can mislead. A high-energy song like Gym Hero showed up for three of my four profiles, and it was not because the system "knew" those people. It was because the numbers happened to line up.

**What I did not expect.** The sticky songs were not "average" songs. They were the five loud ones (Sunrise City, Gym Hero, Rooftop Lights, Storm Runner and Night Drive Loop), because half the catalog is loud and half is quiet and nothing sits in between. When I made energy four times as important as genre, the order for the main pop profile did not change at all, only the scores. That showed me a change can feel important and still not make recommendations better.

**Using AI.** AI tools were fast at the routine parts: reading the CSV, formatting the reasons, and drafting edge-case tests. I still had to check its work by hand. When the weights changed I recalculated the maximum score (7.5 to 8.5) and confirmed no reason string showed a zero or negative number. Some drafts I was given also made claims the data did not support, such as saying the weight change improved results, so I re-ran the numbers before writing anything down.

**How this changes how I see music apps.** A recommendation that feels personal may only reflect what the catalog happens to contain. If a catalog has nothing for a listener, a recommender will still hand them five songs.

**What I would try next.** A much larger catalog, partial credit for related genres and moods, an honest "nothing fits" message, and collaborative filtering.
