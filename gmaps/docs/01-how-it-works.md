# How the Google Maps extractor works

A plain walkthrough of what happens between typing one command and getting a finished market
survey. No prior knowledge of the codebase assumed.

---

## The one-sentence version

For a chosen city and a chosen medical specialty, it searches Google Maps once, reads the whole
results list, and then opens only the clinics that actually belong to that specialty — pulling
their full profile and every review — while recording the rest cheaply from the list itself.

---

## Why one query, not many

An earlier design ran ~25 queries per city (`acne treatment in Guntur`, `psoriasis treatment in
Guntur`, and so on). That was dropped deliberately.

Nobody types *"best psoriasis treatment"* into **Maps** — those are Google **search** behaviours.
On Maps, condition queries mostly return the same clinics the specialist query already found, so
the extra ~24 queries bought a few percent more coverage for several extra hours of scraping and
a large increase in the chance of being throttled.

So: **Maps gets one query. The condition phrasings belong to the Google-search side of the
product.**

The query is composed as:

```
best {specialists} in {city}, {admin area}
→ "best dermatologists in Guntur, Andhra Pradesh"
```

The admin area is always included. A bare town or village name is ambiguous — there are Guntur-like
names in several states and countries — and a mis-resolved location produces a healthy-looking
survey of entirely the wrong market.

---

## The five stages of a run

### 1. Open the search, scroll to the true end of the list

The results feed loads about 20 clinics at a time. The scraper scrolls until the list genuinely
stops growing.

> **This is where the original version failed badly.** It stopped after 12 scrolls and capped
> results at 15 per query, so it captured **34 clinics where the live list holds 97** — roughly a
> third of the market, reported as if it were all of it.

Stopping is decided two ways. Google prints *"You've reached the end of the list"*, which is used
as a fast path — but that sentence is English, so it cannot be trusted in another market. The
authoritative stop is structural: the card count stops increasing for 15 consecutive rounds. The
reason the scroll ended is recorded (`feed_end_reason`) so a truncated feed is visible afterwards
rather than silently assumed complete.

### 2. Read every card, without opening anything

Each result in the list is a "card". Everything on it is read straight from the list — name,
category, rating, review count, partial address, the place ID, whether it's flagged closed, and
whether it offers **Book online**.

This costs nothing. No page is opened at this point.

### 3. Decide who is worth opening

Each card is classified against the specialty as **relevant**, **adjacent**, or **not relevant**
(see `03-queries.md` and `04-architecture.md` for the rules).

This is the key economy of the whole design. Measured cost of opening one clinic:

```
≈ 40 seconds fixed  +  0.18 seconds per review
```

The fixed page-open dominates. So *not opening* an irrelevant clinic saves the entire 40 seconds,
whereas merely skipping its reviews would have saved about two.

Gating on the card was validated before being trusted: across 98 real cards, the card-based
verdict agreed with the opened-page verdict **99% of the time, with zero false negatives** — it
never wrongly skips a clinic you would have wanted.

### 4. Extract, in two tiers

**Relevant and adjacent → full extraction.** Open the place, read the contact block, hours
(hidden behind a dropdown that must be clicked), the About tab, the star histogram, the review
labels, and then **every single review**, sorted newest-first.

**Not relevant → card only.** Name, partial address, category and rating from the list. The page
is never opened. The record is stamped `address_is_partial`, `skipped_reason`, and a
`not_collected` list, so nobody can mistake "we chose not to look" for "the clinic doesn't have
one".

### 5. Write, continuously and safely

Every clinic is written to its own file the moment it finishes, using a write-to-temp-then-rename
so a kill mid-write cannot leave half a file. A summary and a status file are refreshed after
each clinic, which is what the live page reads.

---

## Reading all the reviews

This deserves its own note, because it was the subtlest bug in the project.

Google hands over reviews in bursts with pauses in between. The first implementation gave up after
6 seconds of no new reviews arriving — so it quit during a pause and reported a partial list as
complete. It captured 531 of 638 reviews on one clinic and called it done.

A 137-page PDF capture of that clinic's review list proved every review really was reachable. The
fix was patience: wait **20 seconds** of genuine stillness before concluding the list has ended,
with a 7-minute ceiling per clinic. Result on the same clinic: **639 of 639, with the star
breakdown matching Google's own histogram exactly in all five bands.**

Reviews are also **sorted newest-first** before reading. That is not cosmetic — it is what makes
the next quarterly run cheap. In date order the scraper reads from the top and stops at the first
review it already has. In Google's default "most relevant" order, new and old are interleaved, so
there is no safe stopping point and the entire list must be re-read every quarter.

Customer text and owner replies are told apart structurally: the owner's reply sits inside a
`.CDe7pd` block, the customer's words are outside it. Only the *fact* of a reply is kept — an
owner's marketing copy is not patient sentiment.

---

## What it does when things go wrong

| Situation | Behaviour |
|---|---|
| A clinic page loads stripped (name renders, reviews don't) | Treated as a transport failure, retried once. Never recorded as a clinic with no reviews. |
| A clinic errors entirely | An error stub is written, the browser tab is replaced (a broken page can poison the next one), and the run continues. |
| The run is killed | Every finished clinic is already on disk. Re-running skips them and resumes. |
| A review pane won't open | Recorded as `reviews_error` and counted, not left blank. |

Completeness is stored **inside** each file (`complete: true`), not inferred from the file
existing — an error stub is a file too, and keying on existence would mark failures as finished
and never retry them.

---

## What it does *not* do yet

Stated plainly, because the gaps matter more than the features:

- **A completely failed scrape currently reports success.** If Google changed the results markup,
  the run would find zero clinics and still write `finished: true, errors: 0`. A dashboard would
  show an empty market as fact. *(Known defect, under fix.)*
- **Finished snapshots are not locked.** Nothing refuses a later run writing into an old run's
  directory. *(Known defect, under fix.)*
- Many internal failures are swallowed silently, so "no About section" and "About extraction
  crashed" currently look identical.

See `06-operations.md` for the full known-issues list.
