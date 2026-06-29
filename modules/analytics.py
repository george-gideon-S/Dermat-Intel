"""Step 3 — Analytics engine: data-prep helpers + 14 chart builders.

Charts are kept thin over tested pandas helpers. `build_all()` returns every figure keyed by
name and is empty-data safe (returns a placeholder figure instead of raising).
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

try:
    import config
except ModuleNotFoundError:  # pragma: no cover
    import importlib
    config = importlib.import_module("config")

from modules.vulnerability import aggregate_clinics

POS = "#2563EB"   # positive / primary (blue)
NEG = "#DC2626"   # gap / negative (red)
TIER_COLORS = {"No rating": "#9CA3AF", "Low (<3)": "#DC2626",
               "Mid (3-4)": "#F59E0B", "High (>4)": "#16A34A"}


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and v != v)


def _rating_tier(r) -> str:
    if _missing(r):
        return "No rating"
    if r < 3:
        return "Low (<3)"
    if r <= 4:
        return "Mid (3-4)"
    return "High (>4)"


def _placeholder(msg: str = "No data yet — run the pipeline"):
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=16, color="#6B7280"))
    fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=350)
    return fig


# =========================================================================== helpers
def kpis(result_rows: list[dict]) -> dict:
    u = aggregate_clinics(result_rows)
    if u.empty:
        return {"unique_clinics": 0, "avg_rating": 0.0, "median_reviews": 0,
                "avg_reviews": 0, "pct_with_website": 0.0}
    ratings = u["rating"].dropna()
    reviews = u["user_ratings_total"].dropna()
    has_web = int((u["website"].fillna("").astype(str).str.strip() != "").sum())
    return {
        "unique_clinics": len(u),
        "avg_rating": round(float(ratings.mean()), 2) if not ratings.empty else 0.0,
        "median_reviews": int(reviews.median()) if not reviews.empty else 0,
        "avg_reviews": int(round(reviews.mean())) if not reviews.empty else 0,
        "pct_with_website": round(100 * has_web / len(u), 1),
    }


def category_distribution(query_rows: list[dict]) -> pd.DataFrame:
    if not query_rows:
        return pd.DataFrame(columns=["category", "count"])
    df = pd.DataFrame(query_rows)
    out = df.groupby("category").size().reset_index(name="count")
    return out.sort_values("count", ascending=False).reset_index(drop=True)


def appearance_counts(result_rows: list[dict]) -> pd.DataFrame:
    u = aggregate_clinics(result_rows)
    if u.empty:
        return pd.DataFrame(columns=["name", "appearances", "rating", "user_ratings_total", "website"])
    return u.sort_values("appearances", ascending=False).reset_index(drop=True)


def quadrant_frame(result_rows: list[dict]) -> pd.DataFrame:
    u = aggregate_clinics(result_rows)
    if u.empty:
        return pd.DataFrame(columns=["name", "appearances", "rating", "zone"])
    df = u[["name", "appearances", "rating"]].copy()
    df["rating"] = df["rating"].fillna(0.0)
    med = df["appearances"].median()

    def zone(r):
        high_app = r["appearances"] >= med
        high_rat = r["rating"] >= 3.5
        if high_app and high_rat:
            return "Stars"
        if not high_app and high_rat:
            return "Hidden Gems"
        if high_app and not high_rat:
            return "Vulnerable"
        return "Off-Radar"

    df["zone"] = df.apply(zone, axis=1)
    return df


def presence_funnel(result_rows: list[dict]) -> list[tuple[str, int]]:
    """Cumulative 'online presence completeness' funnel (monotonically non-increasing)."""
    u = aggregate_clinics(result_rows)
    n = len(u)
    if n == 0:
        return [("All clinics", 0)]
    phone = u["formatted_phone_number"].apply(lambda p: not _missing(p) and str(p).strip() != "")
    web = u["website"].fillna("").astype(str).str.strip() != ""
    r4 = u["rating"].fillna(0) > 4
    rev50 = u["user_ratings_total"].fillna(0) > 50
    m1 = phone
    m2 = m1 & web
    m3 = m2 & r4
    m4 = m3 & rev50
    return [("All clinics", n), ("Has phone", int(m1.sum())), ("+ Website", int(m2.sum())),
            ("+ Rating > 4", int(m3.sum())), ("+ Reviews > 50", int(m4.sum()))]


# =========================================================================== charts
def donut_categories(query_rows):
    d = category_distribution(query_rows)
    if d.empty:
        return _placeholder()
    fig = px.pie(d, names="category", values="count", hole=0.5,
                 color="category", color_discrete_map=config.CATEGORY_COLORS,
                 title="Query Category Distribution")
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def top_clinics_bar(result_rows, top=15):
    d = appearance_counts(result_rows).head(top)
    if d.empty:
        return _placeholder()
    d = d.sort_values("appearances")
    fig = px.bar(d, x="appearances", y="name", orientation="h",
                 color="appearances", color_continuous_scale="Blues",
                 title=f"Top {top} Most-Appeared Clinics")
    fig.update_layout(yaxis_title="", coloraxis_showscale=False, height=480)
    return fig


def rating_vs_reviews_scatter(result_rows):
    u = aggregate_clinics(result_rows)
    if u.empty:
        return _placeholder()
    df = u.copy()
    df["tier"] = df["rating"].apply(_rating_tier)
    df["bubble"] = df["appearances"].clip(lower=1)
    df["rating_plot"] = df["rating"].fillna(0)
    fig = px.scatter(df, x="rating_plot", y="user_ratings_total", size="bubble",
                     color="tier", color_discrete_map=TIER_COLORS,
                     hover_name="name", hover_data={"formatted_address": True, "rating_plot": False},
                     title="Rating vs. Review Volume (bubble = search appearances)")
    fig.update_layout(xaxis_title="Rating", yaxis_title="Review count", height=480)
    return fig


def ratings_histogram(result_rows):
    u = aggregate_clinics(result_rows)
    ratings = u["rating"].dropna() if not u.empty else pd.Series([], dtype=float)
    if ratings.empty:
        return _placeholder()
    fig = px.histogram(ratings, nbins=20, title="Distribution of Clinic Ratings",
                       color_discrete_sequence=[POS])
    fig.add_vline(x=float(ratings.mean()), line_dash="dash", line_color=NEG,
                  annotation_text=f"mean {ratings.mean():.2f}")
    fig.update_layout(xaxis_title="Rating", yaxis_title="Clinics", showlegend=False, height=400)
    return fig


def reviews_box_by_category(result_rows):
    if not result_rows:
        return _placeholder()
    df = pd.DataFrame(result_rows)
    df = df[df["status"] != "FETCH_FAILED"] if "status" in df.columns else df
    df = df.dropna(subset=["user_ratings_total"])
    if df.empty:
        return _placeholder()
    fig = px.box(df, x="source_category", y="user_ratings_total", color="source_category",
                 color_discrete_map=config.CATEGORY_COLORS,
                 title="Review Count Distribution by Query Category")
    fig.update_layout(xaxis_title="", yaxis_title="Reviews", showlegend=False, height=420)
    return fig


def clinic_category_heatmap(result_rows, top=20):
    if not result_rows:
        return _placeholder()
    df = pd.DataFrame(result_rows)
    if df.empty or "source_category" not in df.columns:
        return _placeholder()
    df = df[df["name"].astype(str).str.strip() != ""]
    top_names = df["name"].value_counts().head(top).index.tolist()
    df = df[df["name"].isin(top_names)]
    grid = (df.groupby(["name", "source_category"]).size().reset_index(name="appearances"))
    if grid.empty:
        return _placeholder()
    return (
        alt.Chart(grid, title="Clinic × Query-Category Appearances")
        .mark_rect()
        .encode(
            x=alt.X("source_category:N", title="Category"),
            y=alt.Y("name:N", title="Clinic", sort="-x"),
            color=alt.Color("appearances:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["name", "source_category", "appearances"],
        )
        .properties(height=max(300, 22 * len(top_names)))
    )


def ranked_appearances_bar(result_rows, top=20):
    return top_clinics_bar(result_rows, top=top)


def website_presence_stacked_bar(result_rows):
    if not result_rows:
        return _placeholder()
    df = pd.DataFrame(result_rows)
    if df.empty or "source_category" not in df.columns:
        return _placeholder()
    df["has_website"] = df["website"].fillna("").astype(str).str.strip().ne("").map(
        {True: "Has website", False: "No website"})
    grid = df.groupby(["source_category", "has_website"]).size().reset_index(name="count")
    fig = px.bar(grid, x="source_category", y="count", color="has_website", barmode="stack",
                 color_discrete_map={"Has website": POS, "No website": NEG},
                 title="Website Presence by Query Category")
    fig.update_layout(xaxis_title="", yaxis_title="Appearances", height=420)
    return fig


def treemap_reviews(result_rows):
    u = aggregate_clinics(result_rows)
    if u.empty:
        return _placeholder()
    df = u.copy()
    df["tier"] = df["rating"].apply(_rating_tier)
    df["reviews"] = df["user_ratings_total"].fillna(0).clip(lower=0)
    if df["reviews"].sum() == 0:
        return _placeholder("No review data to size the treemap")
    fig = px.treemap(df, path=[px.Constant("All clinics"), "name"], values="reviews",
                     color="tier", color_discrete_map=TIER_COLORS,
                     title="Clinics sized by Review Volume, coloured by Rating Tier")
    fig.update_layout(height=480, margin=dict(t=50, l=10, r=10, b=10))
    return fig


def map_scatter(result_rows):
    u = aggregate_clinics(result_rows)
    if u.empty:
        return _placeholder()
    df = u.dropna(subset=["lat", "lng"]).copy()
    if df.empty:
        return _placeholder("No coordinates available for the map")
    df["tier"] = df["rating"].apply(_rating_tier)
    df["reviews"] = df["user_ratings_total"].fillna(0)
    fig = px.scatter_mapbox(
        df, lat="lat", lon="lng", color="tier", color_discrete_map=TIER_COLORS,
        hover_name="name", hover_data={"rating": True, "reviews": True, "lat": False, "lng": False},
        zoom=11, title="Clinic Map (colour = rating tier)")
    fig.update_layout(mapbox_style="open-street-map", height=520,
                      margin=dict(t=50, l=0, r=0, b=0))
    return fig


def quadrant_scatter(result_rows):
    df = quadrant_frame(result_rows)
    if df.empty:
        return _placeholder()
    med = df["appearances"].median()
    fig = px.scatter(df, x="appearances", y="rating", color="zone", hover_name="name",
                     color_discrete_map={"Stars": "#16A34A", "Hidden Gems": "#2563EB",
                                         "Vulnerable": "#DC2626", "Off-Radar": "#9CA3AF"},
                     title="Competitive Quadrant: Appearances vs. Rating")
    fig.add_vline(x=med, line_dash="dot", line_color="#6B7280")
    fig.add_hline(y=3.5, line_dash="dot", line_color="#6B7280")
    xmax = df["appearances"].max() or 1
    for (zx, zy, label) in [(xmax, 5, "Stars"), (0, 5, "Hidden Gems"),
                            (xmax, 0, "Vulnerable"), (0, 0, "Off-Radar")]:
        fig.add_annotation(x=zx, y=zy, text=label, showarrow=False,
                           font=dict(size=11, color="#374151"), opacity=0.7)
    fig.update_layout(height=480)
    return fig


def no_website_bar(result_rows, top=15):
    u = aggregate_clinics(result_rows)
    if u.empty:
        return _placeholder()
    nw = u[u["website"].fillna("").astype(str).str.strip() == ""]
    if nw.empty:
        return _placeholder("Every clinic has a website 🎉")
    nw = nw.sort_values("appearances", ascending=False).head(top).sort_values("appearances")
    fig = px.bar(nw, x="appearances", y="name", orientation="h",
                 color_discrete_sequence=[NEG],
                 title=f"Clinics With NO Website (top {top} by appearances)")
    fig.update_layout(yaxis_title="", height=460)
    return fig


def presence_funnel_chart(result_rows):
    steps = presence_funnel(result_rows)
    if not steps or steps[0][1] == 0:
        return _placeholder()
    labels = [s[0] for s in steps]
    values = [s[1] for s in steps]
    fig = go.Figure(go.Funnel(y=labels, x=values, marker=dict(color=POS),
                              textinfo="value+percent initial"))
    fig.update_layout(title="Online Presence Completeness", height=420)
    return fig


# =========================================================================== build_all
def _safe(fn, *args):
    try:
        out = fn(*args)
        return out if out is not None else _placeholder()
    except Exception as exc:  # never let one chart break the dashboard
        return _placeholder(f"Chart unavailable: {exc.__class__.__name__}")


def build_all(query_rows: list[dict], result_rows: list[dict]) -> dict:
    """Return every figure keyed by name (empty-data safe)."""
    return {
        "donut": _safe(donut_categories, query_rows),
        "top_clinics": _safe(top_clinics_bar, result_rows),
        "rating_reviews": _safe(rating_vs_reviews_scatter, result_rows),
        "ratings_hist": _safe(ratings_histogram, result_rows),
        "reviews_box": _safe(reviews_box_by_category, result_rows),
        "heatmap": _safe(clinic_category_heatmap, result_rows),
        "ranked_appearances": _safe(ranked_appearances_bar, result_rows),
        "website_stacked": _safe(website_presence_stacked_bar, result_rows),
        "treemap": _safe(treemap_reviews, result_rows),
        "map": _safe(map_scatter, result_rows),
        "quadrant": _safe(quadrant_scatter, result_rows),
        "no_website": _safe(no_website_bar, result_rows),
        "funnel": _safe(presence_funnel_chart, result_rows),
    }
