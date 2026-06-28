import openpyxl
import pytest

from modules.query_generator import (
    build_ai_prompt,
    parse_pasted_queries,
    derive_category,
    save_queries_xlsx,
)


# ---------------------------------------------------------------- build_ai_prompt
def test_prompt_demands_50_and_format():
    p = build_ai_prompt()
    assert "exactly 50" in p.lower()
    assert "comma-separated" in p.lower()
    assert "'best dermatologist in Guntur'" in p  # format example present
    assert "Guntur" in p


# ---------------------------------------------------------------- parse
def test_parse_simple_single_quotes():
    rows = parse_pasted_queries("'best dermatologist in Guntur', 'skin specialist near me'")
    assert [r["search_query"] for r in rows] == [
        "best dermatologist in Guntur",
        "skin specialist near me",
    ]
    assert rows[0]["rank"] == 1 and rows[1]["rank"] == 2


def test_parse_double_quotes_newlines_numbering_brackets():
    raw = '[\n 1. "acne treatment doctor Guntur",\n 2. "dermatologist fees Guntur"\n]'
    rows = parse_pasted_queries(raw)
    assert [r["search_query"] for r in rows] == [
        "acne treatment doctor Guntur",
        "dermatologist fees Guntur",
    ]


def test_parse_dedup_case_insensitive_and_empties():
    rows = parse_pasted_queries("'a clinic', 'A Clinic', '', '  '")
    assert [r["search_query"] for r in rows] == ["a clinic"]


def test_parse_no_quotes_falls_back_to_commas():
    rows = parse_pasted_queries("best dermatologist Guntur, acne treatment Guntur")
    assert [r["search_query"] for r in rows] == [
        "best dermatologist Guntur",
        "acne treatment Guntur",
    ]


def test_parse_empty_returns_empty():
    assert parse_pasted_queries("") == []
    assert parse_pasted_queries("   \n  ") == []


@pytest.mark.parametrize("q,cat", [
    ("acne treatment doctor Guntur", "Condition-Based"),
    ("hair fall specialist Guntur", "Condition-Based"),
    ("dermatologist fees in Guntur", "Pricing"),
    ("best rated skin doctor reviews Guntur", "Trust & Social Proof"),
    ("book dermatologist appointment Guntur", "Appointment & Booking"),
    ("dermatologist vs cosmetologist Guntur", "Comparison"),
    ("skin specialist near me", "Near Me / Local"),
    ("best dermatologist in Guntur", "Discovery"),  # city name must NOT trigger Near-Me
])
def test_derive_category(q, cat):
    assert derive_category(q) == cat


def test_all_rows_have_five_fields():
    rows = parse_pasted_queries("'best dermatologist in Guntur'")
    assert set(rows[0]) == {
        "rank", "search_query", "category", "user_intent", "search_strength_score",
    }
    assert 1 <= rows[0]["search_strength_score"] <= 10


# ---------------------------------------------------------------- save_queries_xlsx
def test_save_xlsx(tmp_path):
    rows = parse_pasted_queries("'best dermatologist in Guntur', 'acne treatment Guntur'")
    out = save_queries_xlsx(rows, str(tmp_path / "q.xlsx"))
    wb = openpyxl.load_workbook(out)
    ws = wb.active
    assert [c.value for c in ws[1]] == [
        "Rank", "Search Query", "Category", "User Intent", "Search Strength Score",
    ]
    assert ws[1][0].font.bold is True
    assert ws.freeze_panes == "A2"
    assert ws.max_row == 3  # header + 2 rows
