# The query, and how relevance is decided

Two questions this file answers: **what do we search for**, and **which results count**.

---

## Part 1 — The query

### One query per run. Deliberately.

```
best {specialists} in {city}, {admin area}
→ "best dermatologists in Guntur, Andhra Pradesh"
```

An earlier design ran roughly 25 queries per city — every condition and treatment phrasing
(`acne treatment in Guntur`, `psoriasis treatment in Guntur`, …). It was removed.

**Why:** nobody searches *"best psoriasis treatment"* on **Maps**. That is Google **search**
behaviour. On Maps, condition queries mostly resurface the clinics the specialist query already
found. The measured trade was several extra hours of scraping and materially more throttling risk,
for a few percent of extra coverage.

Condition phrasings still matter enormously — they belong to the **Google-search half** of the
product, where they measure who ranks for what. They just don't belong here.

### Why the admin area is always included

`"best dermatologists in Guntur"` is ambiguous. Place names repeat across states and countries, and
a mis-resolved location yields a healthy-looking survey of the **wrong market** — the worst kind of
failure, because nothing about the output looks wrong.

So the query carries the qualifier, **and** the URL carries a viewport anchor:

```
/maps/search/best+dermatologists+in+Guntur%2C+Andhra+Pradesh/@16.3067,80.4365,13z/?hl=en&gl=in
```

Two independent geo anchors. If the text is still ambiguous, the coordinates disambiguate it.

### Language

`hl=en` is pinned for **extraction in every market**, worldwide.

Every field the scraper reads is an English label — `"638 reviews"`, `"5 stars, 606 reviews"`,
`"Add website"`, `"mentioned in 24 reviews"`. Letting Google localise the interface would silently
empty all of them, and the run would look successful while producing nothing.

The market's own language belongs in the **query text**, not the interface. A Telugu-language
market can be searched in Telugu while the interface stays English.

> ⚠️ Known risk, not yet verified: whether Google returns an identical result *set* under
> `hl=en` versus `hl=te` for the same query. If it doesn't, a non-English market may be sampled
> slightly differently. Flagged, unproven.

### Changing the query

Set `primary_query` in the specialty pack, or pass `--query` for a one-off. Placeholders:
`{specialists}`, `{specialist}`, `{city}`, `{place}`.

---

## Part 2 — Relevance

A search for dermatologists returns dental clinics, diagnostic labs, general hospitals and
fertility centres. Deciding what counts is what turns a scrape into a market survey.

### Three buckets, never two

| Bucket | Meaning | What happens |
|---|---|---|
| **relevant** | core to the specialty — a Dermatologist, for dermatology | opened, fully extracted |
| **adjacent** | plausibly offers the service but is not a comparable unit — a multispecialty hospital | opened, fully extracted, benchmarked separately |
| **not relevant** | a different trade — dental clinic, diagnostic lab, gym | **never opened**, card data only |

**Why adjacent is its own bucket.** A multispecialty hospital competes for the same patient, so
deleting it hides a real competitor. But ranking a solo practitioner against it on review volume
compares a hospital's whole footfall to one doctor's practice — which says nothing about their
dermatology. Merging it into either side makes the report wrong in a different direction.

### How the decision is made

Category first, name second:

1. **Explicit veto** — the name says another trade (`dental`, `diagnostic`, `piles`) and makes no
   claim to this specialty → not relevant.
2. **Category is relevant** → relevant.
3. **Category is adjacent** → relevant if the name claims the specialty (`Lakshmi Skin Care
   hospital` is a skin clinic despite the category "Hospital"), otherwise adjacent.
4. **Category is irrelevant** → name evidence can lift it *one step* to adjacent, never all the
   way to relevant. Name evidence never fully reverses a negative category.
5. **No category at all** → relevant if the name claims the specialty, otherwise **adjacent** —
   never irrelevant. An unlisted category is our ignorance, not proof the business is unrelated,
   and over-extraction only costs time whereas under-extraction is irreversible data loss.

Every verdict records **why** (`basis`), because a label reached from a business name is weaker
evidence than one reached from Google's own category, and a reader deserves to see which it was.

### Matching is exact, never substring

Categories are compared as whole normalised strings. Substring matching would make the category
`"Clinic"` match `"Dental clinic"` and drag an entire trade into the survey.

Normalisation folds the variants that actually occur: `centre`→`center`, `speciality`→`specialty`,
`paediatric`→`pediatric`, `orthopaedic`→`orthopedic`, hyphens→spaces, plus case and accent folding.

### The same feed, three specialties

The proof that this is genuinely specialty-agnostic — one real 98-card Guntur feed, three packs:

| Specialty | Relevant | Adjacent | Not relevant | Opened | Time saved |
|---|---|---|---|---|---|
| Dermatology | 56 | 30 | 12 | 86 | ~8 min |
| Dentistry | 8 | 33 | 57 | 41 | ~38 min |
| Cardiology | 1 | 29 | 68 | 30 | ~45 min |

Same clinics, radically different verdicts. Adding an eleventh specialty is a JSON file.

### One specialty's noise is another's market

`irrelevant_categories` is **per specialty**. A dental clinic is noise for dermatology and the
entire point for dentistry. Only the genuinely universal exclusions — restaurant, hotel, school,
bank, gym — live in the shared base list, and those are a hard anchor: a restaurant called
"Skin Bar" must never become a clinic.

### Open question

`AIRA IMAGING & DIAGNOSTIC CENTER LLP` is categorised by Google as **Dermatologist**, but the word
"diagnostic" in its name vetoes it to not relevant. Currently a name veto overrides even an
explicit category.

Arguably wrong: if Google says Dermatologist, that is the strongest available evidence, and the
veto should apply only when the category is generic or absent. Affects one clinic here; on other
specialties it could hide real competitors. **Awaiting a decision.**

---

## The ten shipped specialties

`dermatology`, `dentistry`, `cardiology`, `orthopaedics`, `ophthalmology`,
`gynaecology-obstetrics`, `ent`, `paediatrics`, `psychiatry-mental-health`, `physiotherapy`

Each pack carries: relevant / adjacent / irrelevant category lists, `name_strong` and `name_veto`
tokens, facility nouns, and a condition-query list **reserved for the Google-search side**.

> ⚠️ Only dermatology's category vocabulary is verified against live data, from one Indian tier-2
> city. The other nine use plausible Google Business Profile names and should be checked on first
> real use in that specialty.
