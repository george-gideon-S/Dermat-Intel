# Output schema

Exactly what lands on disk, so anything downstream can rely on it.

---

## `places/<place_id>.json` — one clinic

Two shapes exist. **`tier` tells you which**, and it is always present.

### `tier: "full"` — relevant and adjacent clinics

```jsonc
{
  "key": "ChIJCfMja_F1SjoRTfRlLzq-oFA",
  "tier": "full",
  "complete": true,                    // completeness lives IN the file, not in its existence
  "rank": 1,                           // position in the results list
  "place_id": "ChIJCfMja_F1SjoRTfRlLzq-oFA",
  "feature_id": "0x3a4a75f16b23f309:0x50a0be3a2f65f44d",
  "kg_mid": "/g/11f79krp3d",
  "lat": 16.2991916, "lng": 80.4517515,
  "place_url": "https://www.google.com/maps/place/...",
  "captured_at": "2026-08-20T18:02:11",
  "date_anchor": "2026-08-20T18:02:11", // what "3 months ago" is measured from
  "extract_seconds": 136.1,

  // ---- identity
  "name_raw": "Skin Perfect Clinic | Best Dermatologist in Guntur",
  "name_clean": "Skin Perfect Clinic",
  "name_key": "skinperfectclinic",
  "name_dropped": ["Best Dermatologist in Guntur"],
  "name_was_cleaned": true,

  // ---- category and verdict
  "category": "Dermatologist",         // the clinic's primary category (place page)
  "card_category": "Dermatologist",    // the category that matched the search (results list)
  "category_mismatch": false,
  "relevance": "relevant",             // relevant | adjacent | irrelevant
  "basis": "category",                 // WHY - category | name_strong | name_veto | ...

  // ---- contact
  "address": "Old Club Rd, beside Yoda diagnostic lab, Kothapeta, Guntur",
  "plus_code": "7FX2+MP Guntur, Andhra Pradesh",
  "phone": "094909 03999",
  "website": "",
  "website_domain": "", "website_type": "none",
  "has_own_website": false,            // the headline sales signal
  "insecure_http": false,
  "website_matches_name": null,

  // ---- card-only signals (gone once the place is opened, so copied through)
  "has_online_booking": true,
  "booking_url": "https://www.justdial.com/online-consult/...",
  "booking_vendor": "justdial",
  "service_options": ["On-site services"],
  "permanently_closed": false,
  "temporarily_closed": false,
  "review_snippet": "My psoriasis has improved a lot...",
  "is_ad": false,

  // ---- ratings
  "rating": 4.9,
  "reviews_total": 639,
  "rating_histogram": {"5": 607, "4": 10, "3": 4, "2": 3, "1": 15},
  "histogram_sum": 639,
  "histogram_reconciles": true,        // does the breakdown add up to the headline total

  // ---- profile
  "hours": {"Monday": "10 am to 4 pm", "Sunday": "Closed"},
  "about": {"Accessibility": ["Wheelchair accessible entrance"]},
  "topics": {"supportive staff": 34, "pigmentation treatment": 24},
  "has_photos": true,
  "google_profile_gaps": ["Add website"],   // Google itself flagging the gap

  // ---- reviews
  "reviews_captured": 639,
  "reviews_coverage": 1.0,             // captured / total - honesty about completeness
  "owner_replies": 101,
  "sorted_newest": true,               // required for cheap quarterly re-reads
  "stopped_at_known_review": false,
  "reviews_error": "",
  "reviews": [ /* see below */ ],

  "missing_fields": ["website"]
}
```

### `tier: "minimal"` — not-relevant places, never opened

```jsonc
{
  "key": "ChIJ...", "tier": "minimal", "complete": true,
  "rank": 42,
  "name_raw": "Giridhar Dental Clinic", "name_clean": "Giridhar Dental Clinic",
  "card_category": "Dental clinic", "category": "",
  "relevance": "irrelevant", "basis": "name_veto:dental",
  "address": "Main Rd, Guntur",
  "address_is_partial": true,          // the card shows a shortened address
  // no rating, review count, booking, service options or opening status: this business is
  // outside the specialty, so those are facts about a market we are not reporting on
  "extract_seconds": 0.0,
  "skipped_reason": "not relevant to this specialty - not opened",
  "not_collected": ["phone", "website", "plus_code", "hours", "about", "reviews", ...],
  "missing_fields": []
}
```

**`not_collected` versus `missing_fields` is the important distinction.** `not_collected` means we
chose not to look; `missing_fields` means the source had a slot and it was empty. Collapsing them
would let *"we didn't look"* read as *"the clinic doesn't have one"* — for the website field, that
is the difference between a sales prospect and a false alarm.

### Error stub

```jsonc
{ "key": "...", "rank": 17, "name_clean": "...", "complete": false,
  "error": "TimeoutError: ...", "place_url": "..." }
```

`complete: false` means it will be **retried on the next run**. Done-ness is read from inside the
file, never from the file existing — an error stub is a file too.

---

## One review

```jsonc
{
  "review_id": "Ci9DQUlRQUNvZENodH...",   // stable - the key to incremental re-reads
  "author": "Satya Vani",
  "rating": 5,
  "relative_date": "44 minutes ago",      // NEVER absolute - resolve against date_anchor
  "text": "Very good dermatologist and excellent treatment...",
  "has_owner_reply": true                 // the fact only; reply text is not stored
}
```

Reviews with a rating but **no text** are still reviews and are kept — 122 of 639 on one real
clinic. An empty `text` is data, not a failure.

⚠️ **There is no absolute date anywhere in a Google review.** Only `date_anchor` makes
`relative_date` meaningful. Read a record without it and "a week ago" silently means a different
week every time.

---

## `data.json` — the summary the live page reads

An array of compact rows, one per clinic, sorted by rank: identity, category, verdict, contact,
counts, and the missing/not-collected lists. **Full review text is not included** — it lives in
the per-place files and is fetched on demand, which keeps 3-second polling cheap even across tens
of thousands of reviews.

## `status.json`

```jsonc
{ "started_at": 1787229652.9, "elapsed": 6977, "finished": true,
  "done": 98, "total": 98, "to_open": 86, "card_only": 12,
  "errors": 0, "current": "Cure & Care Poly Clinic",
  "query": "best dermatologists in Guntur, Andhra Pradesh",
  "city": "Guntur", "specialty": "Dermatology" }
```

## `feed.json`

Every card exactly as captured, plus `feed_end_reason`
(`end_of_list_sentinel` | `no_growth` | `budget_exhausted` | `max_rounds`).

**`feed_end_reason` is the audit trail for completeness.** A feed that ended on
`budget_exhausted` did not see the whole market, and any market-size figure derived from it must
say so.

## `manifest.json`

What was run: query, city, country, packs, timezone, `hl`/`gl`, start and finish times, and the
place count. Enough to reproduce the run and to judge whether two snapshots are comparable.

---

## Consuming this downstream

- **Join on `place_id`.** Never on name or address.
- **Check `tier`** before expecting phone, hours or reviews.
- **Check `complete`** before treating a record as finished.
- **Check `reviews_coverage`** before calling a review set complete.
- **Check `histogram_reconciles`** before trusting the star breakdown.
- **Check `feed_end_reason`** before quoting a market size.
- **Never compare `relative_date` across snapshots** without resolving through `date_anchor`.
