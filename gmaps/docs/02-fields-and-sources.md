# Every field, and exactly where it comes from

Google Maps shows a clinic's information in four different places, and **which one a field lives
in decides whether we can get it cheaply, expensively, or at all**.

The four sources:

| # | Source | Cost to read | Notes |
|---|---|---|---|
| 1 | **Results list card** | free | already on screen after the search |
| 2 | **Overview tab** | ~10s (opens the page) | the default tab |
| 3 | **Reviews tab** | ~0.18s per review | the expensive one |
| 4 | **About tab** | ~2s | one extra click |

A place must be *opened* to reach sources 2–4, and opening costs ~40 seconds regardless of what
you then read. That single fact drives the whole tiering design.

---

## 1. Results list card — free, and some fields exist ONLY here

Read for every clinic, always. Measured availability over the real 98-card Guntur feed:

| Field | Available | Notes |
|---|---|---|
| `place_id`, `feature_id`, `kg_mid` | 98/98 | the stable identity, survives renaming |
| `lat`, `lng` | 98/98 | from the link, no geocoding needed |
| `name` | 98/98 | raw, before cleaning |
| `card_category` | 98/98 | **query-biased** — see the warning below |
| `card_address` | 96/98 | shortened, not the full address |
| `rating` | 94/98 | |
| `reviews_total` | 74/98 | absent on Google's first render batch; the page has it |
| ~~`status_text`, `open_now`~~ | 88/98 | **not collected** — "Open · Closes 7 pm" is true only at the instant of the scrape, so it is stale an hour later and meaningless in a quarterly snapshot |
| `permanently_closed`, `temporarily_closed` | 4 flagged | |
| **`has_online_booking`** | **6/98** | **exists ONLY here** |
| **`booking_url`, `booking_vendor`** | 6/98 | justdial / remedo / healthplix |
| **`service_options`** | 10/98 | e.g. "On-site services" |
| `review_snippet` | 61/98 | one quoted line |
| `is_ad` | 0 observed | detector present but unverified — no ads in the capture |
| phone | **0/98** | not on the card at any time |
| website | **0/98** | not on the card at any time |

### The three card-only fields

**Book online**, **service options** and **closed status** appear on the results list and are
*gone once you open the place*. If they are not copied out of the card at read time, they are lost
permanently. Both extraction tiers carry them through.

`has_online_booking` is a genuine commercial signal: a clinic wired into an online booking system
is further along digitally than one reachable only by phone. The **vendor** matters too — a
JustDial booking link means the clinic is renting someone else's funnel, the same
borrowed-versus-owned distinction that separates an aggregator profile from a real website.

### ⚠️ The card category is query-biased

The card shows the category that **matched your search**; the place page shows the clinic's
**primary** category. Measured disagreement: **12 of 98 = 12.2%**.

```
card = Dermatologist    page = Skin care clinic   (×5)
card = Skin care clinic page = Dental clinic
card = Doctor           page = General hospital
```

Both are stored (`card_category` and `category`) and disagreement is flagged
(`category_mismatch`). Neither is "wrong" — they answer different questions.

---

## 2. Overview tab — the contact and profile block

Requires opening the place.

| Field | Selector / source | Notes |
|---|---|---|
| `name_raw` → `name_clean` | `h1.DUwDvf` | see name cleaning below |
| `category` | category button | the clinic's primary category |
| `address` | `[data-item-id="address"]` | full address |
| `phone` | `[data-item-id^="phone:tel:"]` | **only available here** |
| `website` | `[data-item-id="authority"]` | **absent means genuinely no website** |
| `plus_code` | `[data-item-id="oloc"]` | Google's grid reference |
| `rating`, `reviews_total` | aria-labels | |
| `rating_histogram` | `"5 stars, 606 reviews"` labels | the 5/4/3/2/1 breakdown |
| `topics` | `[role="radio"]` "mentioned in N reviews" | Google's own review labels, with counts |
| `hours` | click `[jsaction*="openhours"]` → `table.eK4R0e` | **hidden behind a dropdown arrow** |
| `has_photos` | photo buttons | presence only, not a count |
| `google_profile_gaps` | `span.DkEaL` starting "Add " | Google itself saying the profile is incomplete |

Three of these deserve emphasis:

**The star histogram** separates a 4.9 built on 638 reviews from a 4.9 built on 9. Without it,
rating is nearly useless as a discriminator — in the Guntur market almost every clinic sits
between 4.6 and 5.0.

**Topics** are Google's own tally of what patients mention, with counts, computed for free:
`supportive staff 34`, `pigmentation treatment 24`, `laser toning 14`. This is pre-computed
sentiment analysis nobody has to pay for.

**`google_profile_gaps`** is Google displaying *"Add website"* — an independent confirmation of the
single biggest sales signal in the report.

---

## 3. Reviews tab — the expensive source

Requires opening the place, clicking through to reviews, sorting, and scrolling to the end.

Per review:

| Field | Notes |
|---|---|
| `review_id` | stable — this is what makes quarterly incremental re-reads possible |
| `author` | |
| `rating` | 1–5 |
| `relative_date` | **"3 months ago" — never an absolute date** |
| `text` | full text, after expanding "More" |
| `has_owner_reply` | **the fact only; reply text is deliberately not stored** |

**Reviews with a rating but no text are still reviews** and are captured — 122 of Skin Perfect
Clinic's 639 were rating-only.

⚠️ **There is no absolute date anywhere in a review.** Only "a week ago". Every record therefore
carries `date_anchor` (the capture timestamp); without it, "a week ago" silently means something
different every time it's read.

---

## 4. About tab — service attributes

One extra click. Grouped attributes such as accessibility, service options, payment methods and
amenities. Stored as raw labels grouped by heading, because the vocabulary varies by trade and by
country — normalising it now would discard detail we cannot yet interpret.

---

## Derived fields (computed, not scraped)

| Field | What it does |
|---|---|
| `name_clean` | strips SEO padding: `"Chandana Skin Clinic \| Dermatologist \| Laser Scar Treatment"` → `"Chandana Skin Clinic"`. 17 of 98 names needed it; 81 were correctly left alone. A hyphen is **not** a separator — `"- kothapeta"` marks a branch that distinguishes two real locations. |
| `name_dropped` | what was removed, so the cleaning is auditable |
| `website_type` | own_domain / chain_corporate / google_business_site / aggregator_profile / social_profile / link_aggregator / none |
| `has_own_website` | the headline sales signal. A Practo profile is **not** a website. |
| `relevance` + `basis` | relevant / adjacent / not relevant, and *why* |
| `reviews_coverage` | captured ÷ total — honesty about completeness |
| `category_mismatch` | card and page disagree |

`name_raw` is never overwritten. It is the provenance field if a clinic disputes the report, and
how much keyword padding a clinic uses is itself a signal about their SEO posture.

---

## Two kinds of "missing", kept apart

| Field | Meaning |
|---|---|
| `missing_fields` | the source had a slot for it and it was genuinely empty |
| `not_collected` | we chose not to open the page, so we never looked |

Collapsing these would let *"we didn't look"* read as *"the clinic doesn't have one"* — which, for
the website field, is the difference between a sales prospect and a false alarm.
