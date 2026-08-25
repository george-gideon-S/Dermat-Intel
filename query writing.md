# Query writing

The rules a search query must follow before it can enter a run, and the categories a query
gets sorted into once it does.

These are not style preferences. A query set is the instrument we measure a market with, and a
bad query does not produce a wrong number you can spot — it produces a plausible number that
means something else. Every rule below exists because of a specific way that happens.

Enforced in code: `modules/query_builder.py` (rules 1–5, as hard gates in `validate()`) and
`modules/query_generator.py` (`derive_category`, rules 6–11). Change a rule here and change it
there, or the two will drift.

---

## Part 1 — What a query may say

### Rule 1 · Never use "near me"

`near me`, `nearby`, `closest`, `in my area` and their variants resolve against the *searcher's*
location. The result set then describes wherever the scraper happens to be sitting, not the
market. Two runs from two places are no longer comparable, which destroys the time series.

> ✗ `dermatologist near me`  ✓ `dermatologist in Guntur`

### Rule 2 · Every query names the city

Measured 2026-08-18: **Google ignores the `uule` location parameter.** This machine's IP
geolocates to Vijayawada, ~30 km from Guntur. A query that does not name the city returns a
perfectly healthy-looking SERP for the wrong city — the worst kind of failure, because nothing
about it looks broken.

> ✗ `best skin doctor`  ✓ `best skin doctor in Guntur`

### Rule 3 · No sub-places in a small city

Do not name a neighbourhood, locality, street or landmark when the market is a small city or
town. Guntur is small: patients there search the city, not the colony. Splitting a small market
into slivers measures a street rather than the city, and each sliver returns a near-random
subset of the same clinics.

> ✗ `dermatologist in guntur kothapet`
> ✗ `skin specialist in guntur lakshmipuram`
> ✓ `dermatologist in Guntur`

Controlled per market by `allow_locality_queries` in the geography pack — `false` for Guntur.
For a genuine metro (Hyderabad, Bengaluru) where patients really do search by area, set it
`true` and the locality queries come back. The `localities[]` list stays in the pack either
way; it is still used for address matching.

### Rule 4 · Never name a clinic or a doctor

A query that names a business is not a market measurement — it is a lookup. Whoever is named
wins it by definition, and their "visibility" in that query says nothing about whether anyone
would have found them.

> ✗ `kavitha skin doctor in guntur`
> ✗ `krishnamurthy skin specialist in guntur`
> ✓ `lady skin doctor in guntur`  ✓ `best skin specialist in guntur`

Google's autocomplete suggests these constantly, so this is enforced by an **allowlist**: every
word in a query must be in the specialty's vocabulary, the city name, or the generic word list
in `query_builder._GENERIC_VOCAB`. An unrecognised word is treated as a proper noun and the
query is rejected. If a legitimate query is being blocked, the fix is to add its word to the
vocabulary — never to loosen the check.

### Rule 5 · Ask each condition several ways

Patients phrase the same need very differently. One phrasing per condition under-samples the
market and makes whoever happens to rank for that one phrasing look dominant.

> `hair fall treatment in Guntur` · `hair loss treatment in Guntur` · `baldness treatment in Guntur`
> · `hair fall doctor in Guntur`

The builder guarantees this by ordering: every condition gets its first phrasing before any
gets a second, so a small threshold degrades by asking everything once rather than by dropping
whole conditions off the end.

---

## Part 2 — Which category a query belongs to

Six categories. They are assigned automatically from the query's wording, in the order below —
**first match wins**, so the order *is* the rule.

| # | Category | A query lands here when it… |
|---|---|---|
| 1 | **Pricing** | asks what something costs — `cost`, `price`, `fees`, `charges`, `cheap`, `affordable` |
| 2 | **Appointment & Booking** | wants to book — `appointment`, `book`, `consultation`, `timings` |
| 3 | **Product-Based** | wants a thing, not a visit — `machine`, `device`, `cream`, `serum`, `shampoo`, `tablet`, `oil` |
| 4 | **Doctor-Based** | names a condition **and** a practitioner |
| 5 | **Condition-Based** | names a condition **or** a treatment |
| 6 | **Discovery** | anything else — generic search for a clinic or specialist |

### Rule 6 · A treatment makes it Condition-Based, never Discovery

If a query names a treatment or procedure, the patient is describing **what they want done**.
That is condition intent, even when no condition is spelled out.

> `laser hair removal in Guntur` → **Condition-Based** (not Discovery)
> `hair transplant in Guntur` → **Condition-Based**
> `scalp treatment in Guntur` → **Condition-Based**
> `botox treatment in Guntur` → **Condition-Based**

### Rule 7 · A machine, tool or product is Product-Based

If the query is shopping for a thing rather than for care, it belongs in its own bucket. These
queries usually return e-commerce and manufacturer pages, so counting them as clinic discovery
would drag every clinic's visibility down for searches no clinic could ever win.

> `best laser machine for hair removal in Guntur` → **Product-Based**
> `acne cream in Guntur` → **Product-Based**

### Rule 8 · A condition plus a practitioner is Doctor-Based

If the patient names a complaint **and** asks for a person — `doctor`, `specialist`,
`dermatologist`, `surgeon` — they are looking for who treats it, not what the treatment is.
This is the highest-value category commercially: the searcher has a problem and wants a name.

> `best hair fall doctor in Guntur` → **Doctor-Based**
> `acne doctor in Guntur` → **Doctor-Based**
> `psoriasis specialist in Guntur` → **Doctor-Based**
> but `dermatologist in Guntur` → **Discovery** (a practitioner, but no condition)

### Rule 9 · Trust and social proof are Discovery

Retired as a separate category. `best rated dermatologist in Guntur` is the same intent as
`best dermatologist in Guntur` wearing a different hat — the searcher is discovering options
and using ratings as the sort order. Splitting them fragmented the discovery count without
telling us anything new.

> `best rated skin doctor in Guntur` → **Discovery**
> `dermatologist reviews Guntur` → **Discovery**

### Rule 10 · Comparison is retired

It was never a real patient intent — it existed because one template produced
`best {facility} or {specialist} in {city}`, and the word "or" then matched a comparison rule.
Both the template and the category are gone. Such queries are **Discovery**.

### Rule 11 · Money and booking outrank everything

`hair transplant cost in Guntur` names a treatment, but the searcher is asking a price
question. Pricing and booking are checked first for exactly this reason.

---

## Applying a rule change to an existing run

Rules change; runs already on disk do not. To bring one into line:

```bash
python tools/apply_query_rules.py --run last --dry-run
```

It reports what would be dropped and re-categorised. Without `--dry-run` it rewrites the query
set and re-stamps the fingerprint the runners check.

Two properties it holds to:

- **Ranks are never renumbered.** The fetch log, saved HTML and screenshots are keyed by rank;
  shifting them would re-attribute captured SERPs to different queries. Dropped ranks leave
  gaps, and their captured files stay on disk unreferenced rather than deleted.
- **The yield will move, and that is not progress.** Dropping five already-captured queries
  took the Guntur run from 82/100 to 77/95. Nothing was captured in between — the denominator
  got smaller and more honest.

---

## Adding a market or a specialty

Everything above is data, not code:

- **Geography pack** (`packs/geography/*.json`) — `city`, `city_tokens`, `localities`, and
  `allow_locality_queries` (rule 3).
- **Specialty pack** (`packs/specialty/*.json`) — `conditions[]` and `treatments[]` with their
  phrasings (rule 5), `specialist_synonyms`, and `phrasing_templates` per category.

A new city that is genuinely large should set `allow_locality_queries: true`. A new specialty
needs at least two phrasings per condition — the pack loader refuses one, because a single
phrasing cannot satisfy rule 5.
