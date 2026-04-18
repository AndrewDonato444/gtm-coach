"""Tests for the visual brief layout helpers (brief_layout.py).

Test ID prefix: BL (brief layout).

These cover:
  - compute_brief_metrics: deterministic stats computed from the snapshot
  - parse_brief_sections: H2-marker section splitter for the brief markdown
  - format_arr: human-readable currency formatting for the metrics row
"""

from datetime import date

import pandas as pd
import pytest

from brief_layout import (
    compute_brief_metrics,
    parse_brief_sections,
    format_arr,
)


# ────────────────────────────────────────────────────────────────────────
# format_arr
# ────────────────────────────────────────────────────────────────────────


# BL-001: thousands formatted with K suffix
def test_format_arr_thousands():
    assert format_arr(412000) == "$412K"


# BL-002: millions formatted with M suffix and one decimal
def test_format_arr_millions():
    assert format_arr(1_850_000) == "$1.85M"


# BL-003: round millions trim trailing zero
def test_format_arr_round_millions():
    assert format_arr(2_000_000) == "$2M"


# BL-004: zero
def test_format_arr_zero():
    assert format_arr(0) == "$0"


# BL-005: None passes through to placeholder
def test_format_arr_none():
    assert format_arr(None) == "—"


# BL-006: small amounts under 1000 just print the number
def test_format_arr_small():
    assert format_arr(750) == "$750"


# ────────────────────────────────────────────────────────────────────────
# compute_brief_metrics
# ────────────────────────────────────────────────────────────────────────


def _df_with(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# BL-101: total_accounts counts all rows regardless of other columns
def test_metrics_total_accounts():
    df = _df_with([{"Account Name": f"Co{i}"} for i in range(56)])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["total_accounts"] == 56


# BL-102: arr_at_risk sums ARR for accounts renewing in next 120 days
def test_metrics_arr_at_risk_sums_red_zone_only():
    df = _df_with([
        # In Red Zone (within 120 days of 2026-04-18 → up to 2026-08-16)
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 412000, "Customer Renewal Date": "2026-05-12", "Open Opp?": "N"},
        {"Account Name": "B", "Active Subscriptions ARR Rollup": 890000, "Customer Renewal Date": "2026-06-15", "Open Opp?": "N"},
        # Outside Red Zone
        {"Account Name": "C", "Active Subscriptions ARR Rollup": 1_000_000, "Customer Renewal Date": "2026-12-01", "Open Opp?": "N"},
        {"Account Name": "D", "Active Subscriptions ARR Rollup": 500_000, "Customer Renewal Date": "2027-05-12", "Open Opp?": "N"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["arr_at_risk"] == 412000 + 890000


# BL-103: red_zone_fires counts no-open-opp accounts in next 120 days
def test_metrics_red_zone_fires_count():
    df = _df_with([
        # Fires (no opp + in red zone)
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2026-05-01", "Open Opp?": "N"},
        {"Account Name": "B", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2026-06-01", "Open Opp?": ""},
        # Has opp = not a fire
        {"Account Name": "C", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2026-05-15", "Open Opp?": "Y"},
        # Outside red zone = not counted
        {"Account Name": "D", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2027-01-01", "Open Opp?": "N"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["red_zone_fires"] == 2


# BL-104: days_to_next_renewal returns smallest positive day-count
def test_metrics_days_to_next_renewal():
    df = _df_with([
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2026-05-12", "Open Opp?": "N"},
        {"Account Name": "B", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2026-04-30", "Open Opp?": "N"},
        {"Account Name": "C", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2027-01-01", "Open Opp?": "Y"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    # 2026-04-30 is 12 days from 2026-04-18
    assert m["days_to_next_renewal"] == 12


# BL-105: empty Red Zone yields 0/0 but days_to_next_renewal still computes
def test_metrics_empty_red_zone():
    df = _df_with([
        # All renewals well outside the 120-day window
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2027-01-01", "Open Opp?": "N"},
        {"Account Name": "B", "Active Subscriptions ARR Rollup": 200, "Customer Renewal Date": "2027-06-01", "Open Opp?": "Y"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["arr_at_risk"] == 0
    assert m["red_zone_fires"] == 0
    # 2027-01-01 is 258 days from 2026-04-18
    assert m["days_to_next_renewal"] == 258


# BL-106: past renewal dates excluded from days_to_next_renewal
def test_metrics_days_ignores_past_renewals():
    df = _df_with([
        # Past renewals — should be ignored
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2025-12-15", "Open Opp?": "Y"},
        # Future renewal
        {"Account Name": "B", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2026-06-01", "Open Opp?": "Y"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    # 2026-06-01 is 44 days from 2026-04-18
    assert m["days_to_next_renewal"] == 44


# BL-107: missing Customer Renewal Date column degrades cleanly
def test_metrics_missing_renewal_date_column():
    df = _df_with([
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 412000, "Open Opp?": "N"},
        {"Account Name": "B", "Active Subscriptions ARR Rollup": 890000, "Open Opp?": "Y"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["total_accounts"] == 2
    assert m["arr_at_risk"] is None
    assert m["red_zone_fires"] is None
    assert m["days_to_next_renewal"] is None


# BL-108: missing ARR column → arr_at_risk None, others compute
def test_metrics_missing_arr_column():
    df = _df_with([
        {"Account Name": "A", "Customer Renewal Date": "2026-05-12", "Open Opp?": "N"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["total_accounts"] == 1
    assert m["arr_at_risk"] is None
    assert m["red_zone_fires"] == 1
    assert m["days_to_next_renewal"] is not None


# BL-109: missing Open Opp? column → red_zone_fires None
def test_metrics_missing_open_opp_column():
    df = _df_with([
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 100000, "Customer Renewal Date": "2026-05-12"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["red_zone_fires"] is None
    assert m["arr_at_risk"] == 100000


# BL-110: no future renewals → days_to_next_renewal is None
def test_metrics_no_future_renewals():
    df = _df_with([
        {"Account Name": "A", "Active Subscriptions ARR Rollup": 100, "Customer Renewal Date": "2025-01-01", "Open Opp?": "Y"},
    ])
    m = compute_brief_metrics(df, today=date(2026, 4, 18))
    assert m["days_to_next_renewal"] is None


# ────────────────────────────────────────────────────────────────────────
# parse_brief_sections
# ────────────────────────────────────────────────────────────────────────


CANONICAL_BRIEF = """Five Red Zone renewals totaling $1.85M in ARR have no open opportunity — that's the week's agenda.

## 🔴 The Fires

Morrison Logistics — $412K — renews 5/12 (24 days)

This is the clock-is-ticking fire. No opp, no CSM, no ESA, no notes.

## 🟠 The Leverage Plays

Charon Robotics ($1.8M, June 2027) — 15% PI, no Assurance.

## 🟢 The Slow Burns

Whitestone Energy — $445K — renewed 12/19. Today is April 18. Call this week.

## What You Don't Know

- Hemlock Industries' Open Opp status
- Why Vega has zero whitespace at $680K Enterprise
"""


# BL-201: canonical brief parses into 5 sections with correct kinds
def test_parse_canonical_brief_kinds():
    sections = parse_brief_sections(CANONICAL_BRIEF)
    assert len(sections) == 5
    kinds = [s["kind"] for s in sections]
    assert kinds == ["headline", "fires", "leverage", "slow_burns", "questions"]


# BL-202: headline section captures everything before the first H2
def test_parse_headline_captures_intro():
    sections = parse_brief_sections(CANONICAL_BRIEF)
    headline = sections[0]
    assert headline["kind"] == "headline"
    assert "Five Red Zone renewals" in headline["body"]
    # Headline has no source heading (it's pre-H2 content)
    assert headline["heading"] == "Today's Headline"


# BL-203: section heading text preserved verbatim
def test_parse_preserves_heading_text():
    sections = parse_brief_sections(CANONICAL_BRIEF)
    headings = {s["heading"] for s in sections if s["kind"] != "headline"}
    assert "🔴 The Fires" in headings
    assert "🟠 The Leverage Plays" in headings
    assert "🟢 The Slow Burns" in headings
    assert "What You Don't Know" in headings


# BL-204: section bodies preserve their content verbatim
def test_parse_preserves_section_bodies():
    sections = parse_brief_sections(CANONICAL_BRIEF)
    fires = next(s for s in sections if s["kind"] == "fires")
    assert "Morrison Logistics" in fires["body"]
    assert "clock-is-ticking fire" in fires["body"]


# BL-205: ordering matches source brief
def test_parse_preserves_source_order():
    # Reverse the canonical order in the source — output should reflect input order
    reordered = """## 🟢 The Slow Burns

Whitestone

## 🔴 The Fires

Morrison
"""
    sections = parse_brief_sections(reordered)
    kinds = [s["kind"] for s in sections]
    assert kinds == ["slow_burns", "fires"]


# BL-206: unrecognized H2 sections still appear (kind='other')
def test_parse_unrecognized_section_preserved():
    brief = """## 🔴 The Fires

Morrison Logistics — fire

## The pattern you need to diagnose

Three of your top accounts are missing Assurance — that's a pattern.

## 🟢 The Slow Burns

Whitestone
"""
    sections = parse_brief_sections(brief)
    assert len(sections) == 3
    kinds = [s["kind"] for s in sections]
    assert kinds == ["fires", "other", "slow_burns"]
    other = next(s for s in sections if s["kind"] == "other")
    assert other["heading"] == "The pattern you need to diagnose"
    assert "Three of your top accounts" in other["body"]


# BL-207: brief with no H2 markers falls back to single unstructured section
def test_parse_no_h2_markers_falls_back():
    brief = "Just some prose with no headers at all. Single block."
    sections = parse_brief_sections(brief)
    assert len(sections) == 1
    assert sections[0]["kind"] == "unstructured"
    assert sections[0]["body"] == brief


# BL-208: empty brief returns empty list
def test_parse_empty_brief():
    assert parse_brief_sections("") == []


# BL-209: whitespace-only brief returns empty list
def test_parse_whitespace_only_brief():
    assert parse_brief_sections("   \n\n  ") == []


# BL-210: alternative phrasing "What I Don't Know" also detected as questions
def test_parse_what_i_dont_know_variant():
    brief = """## 🔴 The Fires

Acme

## What I Don't Know

- a question
"""
    sections = parse_brief_sections(brief)
    assert sections[-1]["kind"] == "questions"


# BL-211: section detection is keyword-based when emoji absent
def test_parse_keyword_based_detection_no_emoji():
    brief = """## Fires

Acme

## Strategy Zone Plays

Globex
"""
    sections = parse_brief_sections(brief)
    kinds = [s["kind"] for s in sections]
    assert kinds == ["fires", "leverage"]


# BL-212: H1, H3, H4 markers do not split sections (only H2)
def test_parse_only_h2_splits():
    brief = """# Top Title

intro paragraph

## 🔴 The Fires

### Sub-heading inside Fires

Morrison

#### Even deeper

Some content

## 🟢 The Slow Burns

Whitestone
"""
    sections = parse_brief_sections(brief)
    # headline + fires + slow_burns; the H3/H4 inside fires don't split it
    kinds = [s["kind"] for s in sections]
    assert kinds == ["headline", "fires", "slow_burns"]
    fires = sections[1]
    assert "Sub-heading inside Fires" in fires["body"]
    assert "Even deeper" in fires["body"]
