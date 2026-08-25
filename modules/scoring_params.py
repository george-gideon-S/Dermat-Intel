"""Scoring saturation constants, derived from the run's own query counts.

The scoring constants were tuned for one run shape and then hardcoded. `DEMAND_FULL = 25`
carried the comment "appearing in 25+ of 50 searches" — it is a HALF, not the number 25.
`OWNED_FULL = 6` and friends were "tuned for the ~80-query screenshot corpus". Change the
query count and those numbers silently mean something else: saturation arrives sooner, every
clinic looks more visible, and two snapshots stop being comparable while still presenting as
plain integers.

So they become functions of the three denominators, which are NOT interchangeable:

  * `maps_query_count`  — Maps queries run          (demand: how many searches a clinic appears in)
  * `captured_serps`    — SERPs actually captured   (every per-clinic web rate)
  * `total_queries`     — queries in the set        (market coverage claims only)

June's run was 50 / 78 / 80. Dividing a per-clinic web rate by 80 instead of 78 quietly
penalises every clinic for two SERPs nobody captured; claiming market coverage against 78
overstates it. Derivation at (50, 78, 80) reproduces the shipped constants exactly, so
snapshot #1 keeps its meaning — that equality is pinned by a test.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

SCORING_VERSION = "params-1"

# The reference run the original constants were tuned against.
REF_MAPS_QUERIES = 50
REF_SERPS = 78
REF_TOTAL_QUERIES = 80

# Reference constant values at the reference denominators.
REF_DEMAND_FULL = 25       # half of REF_MAPS_QUERIES
REF_OWNED_FULL = 6
REF_BORROWED_FULL = 12     # 2x owned
REF_PLACES_FULL = 8
REF_BREADTH_FULL = 10

# Floors. A five-SERP run must not make a single appearance mean "fully visible" — that would
# hand a clinic full marks for noise.
MIN_OWNED_FULL = 3
MIN_PLACES_FULL = 4
MIN_BREADTH_FULL = 5
MIN_DEMAND_FULL = 1


def _scaled(ref: int, denominator: int, ref_denominator: int, floor: int) -> int:
    if denominator <= 0:
        return max(floor, ref)
    return max(floor, int(round(ref * denominator / float(ref_denominator))))


@dataclass(frozen=True)
class ScoringParams:
    """Saturation points for one run, plus the denominators that produced them."""

    maps_query_count: int
    captured_serps: int
    total_queries: int

    DEMAND_FULL: int
    OWNED_FULL: int
    BORROWED_FULL: int
    PLACES_FULL: int
    BREADTH_FULL: int

    BORROWED_CREDIT: float = 0.35
    RATING_THRESHOLD: float = 4.8      # market-calibrated; pack-overridable

    @classmethod
    def derive(cls, maps_query_count: int, captured_serps: int,
               total_queries: int, rating_threshold: float = 4.8) -> "ScoringParams":
        owned = _scaled(REF_OWNED_FULL, captured_serps, REF_SERPS, MIN_OWNED_FULL)
        return cls(
            maps_query_count=int(maps_query_count or 0),
            captured_serps=int(captured_serps or 0),
            total_queries=int(total_queries or 0),
            # "half the searches" is the actual rule the 25 encoded.
            DEMAND_FULL=max(MIN_DEMAND_FULL, int(round(0.5 * (maps_query_count or REF_MAPS_QUERIES)))),
            OWNED_FULL=owned,
            BORROWED_FULL=2 * owned,
            PLACES_FULL=_scaled(REF_PLACES_FULL, captured_serps, REF_SERPS, MIN_PLACES_FULL),
            BREADTH_FULL=_scaled(REF_BREADTH_FULL, captured_serps, REF_SERPS, MIN_BREADTH_FULL),
            RATING_THRESHOLD=rating_threshold,
        )

    @classmethod
    def legacy(cls) -> "ScoringParams":
        """The June run's parameters — used for `params=None` and for scoring snapshot #1."""
        return cls.derive(REF_MAPS_QUERIES, REF_SERPS, REF_TOTAL_QUERIES)

    # --- denominator discipline: one method per denominator, so a caller cannot pick wrong
    def maps_rate(self, appearances) -> float:
        """Share of MAPS queries a clinic appeared in."""
        n = self.maps_query_count or REF_MAPS_QUERIES
        return float(appearances or 0) / n

    def web_rate(self, appearances) -> float:
        """Share of CAPTURED SERPs a clinic appeared in — never total_queries."""
        n = self.captured_serps or REF_SERPS
        return float(appearances or 0) / n

    def coverage_rate(self, captured) -> float:
        """Share of the FULL query set that was captured — a market-level claim."""
        n = self.total_queries or REF_TOTAL_QUERIES
        return float(captured or 0) / n

    def as_manifest(self) -> dict:
        return {"scoring_version": SCORING_VERSION, **asdict(self)}


def resolve(params: "ScoringParams | None") -> "ScoringParams":
    """Every scoring entry point starts here, so `params=None` keeps historical behaviour."""
    return params if params is not None else ScoringParams.legacy()


def from_manifest(manifest: dict) -> ScoringParams:
    """Rebuild the parameters a stored snapshot was scored with, for comparable re-rendering."""
    d = (manifest or {}).get("denominators") or {}
    scoring = (manifest or {}).get("scoring") or {}
    return ScoringParams.derive(
        maps_query_count=d.get("maps_query_count") or REF_MAPS_QUERIES,
        captured_serps=d.get("captured_serps") or REF_SERPS,
        total_queries=d.get("total_queries") or REF_TOTAL_QUERIES,
        rating_threshold=scoring.get("RATING_THRESHOLD", 4.8),
    )
