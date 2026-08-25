# Google Maps market-survey extractor

For one **city** and one **specialty**, this builds a complete picture of the local market: every
clinic Google Maps lists, their contact details and profile, and every review — with the
businesses that don't belong to the specialty identified and skipped cheaply.

```bash
"C:/Users/SALE PITCHAIAH/AppData/Local/Programs/Python/Python310/python.exe" gmaps/run.py --geo guntur-ap --specialty dermatology
```

> Use the full interpreter path, and invoke by path — `python -m gmaps.run` does not work on this
> machine. See [06-operations.md](docs/06-operations.md).

---

## Documentation

| File | What it covers |
|---|---|
| [01 — How it works](docs/01-how-it-works.md) | the run explained end to end, in plain language |
| [02 — Fields and sources](docs/02-fields-and-sources.md) | every field, and which tab or list it comes from |
| [03 — Queries and relevance](docs/03-queries-and-relevance.md) | what we search for, and which results count |
| [04 — Architecture](docs/04-architecture.md) | files, modules, data flow, identity, paths |
| [05 — Output schema](docs/05-output-schema.md) | exactly what lands on disk |
| [06 — Operations](docs/06-operations.md) | running, resuming, costs, **and known defects** |

---

## The idea in one page

**One query.** `best dermatologists in Guntur, Andhra Pradesh`. Condition searches like *"psoriasis
treatment"* are Google-**search** behaviour, not Maps behaviour, and belong to the other half of
the product.

**Read the whole list.** Scroll until it genuinely ends. The first version stopped early and found
**34 clinics where the market holds 97** — a third of the market, reported as all of it.

**Decide before spending.** Every result card carries a category, so relevance is judged for free,
before any page is opened. Validated across 98 real cards: 99% agreement with the opened-page
verdict, and **zero false negatives**.

**Two tiers.** Relevant and adjacent clinics are opened and fully extracted, including every
review. Not-relevant ones are recorded from the card alone and never opened — worth ~40 seconds
each, since the page-open dominates the cost.

**Three buckets, not two.** *Relevant*, *adjacent* and *not relevant*. A multispecialty hospital
competes for the same patient but is not a comparable business unit, so it is neither deleted nor
ranked against a solo practitioner.

**Any specialty, any market.** Ten specialties ship as data; a new one is a JSON file. Extraction
is pinned to an English interface in every market because every field read is an English label,
while the query text carries the market's own language.

---

## What a real run produced

Guntur dermatology, 116 minutes:

| | |
|---|---|
| Places found | **97** (vs 34 before) |
| Relevant / adjacent / not relevant | 52 / 34 / 11 |
| Reviews captured | **12,777** |
| Clinics at exactly 100% review coverage | 88 of 93 |
| **Clinics with no website of their own** | **75** |

Verified against an independent 137-page manual capture of one clinic: **639 reviews extracted
versus 639 reported by Google**, with the star breakdown matching in all five bands.

---

## Status

Working and validated on real data. Two **critical defects** remain open — a completely failed
scrape currently reports success, and finished snapshots are not yet immutable. Both are described
in [06-operations.md](docs/06-operations.md#known-defects--read-before-trusting-a-run). Read that
section before treating any run as authoritative.

Previous implementation and the raw captured DOM used to verify every selector are preserved in
`archive/gmaps_v1_2026-08-20/`.
