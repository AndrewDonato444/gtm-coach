"""Tests for column-shape validation (validation.py).

Test ID prefix: SVC (services layer, no UI or DB involvement).
Range: SVC-401–SVC-419 (SVC-001–SVC-399 reserved for db.py tests).
"""

import pytest

from validation import (
    validate_columns,
    STANDARD_FIELDS,
    _STRATEGY_BUCKET_EXACT,
    _PRICE_INCREASE_VARIANTS,
    _PRICE_INCREASE_CANONICAL,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

# Full "ideal" column set: all standard + all strategy buckets, using "%"
# variant for Price Increase.
FULL_COLUMNS: list[str] = (
    STANDARD_FIELDS
    + [_PRICE_INCREASE_VARIANTS[0]]   # "Price Increase %"
    + _STRATEGY_BUCKET_EXACT
)

# Full column set using "$" variant instead.
FULL_COLUMNS_DOLLAR: list[str] = (
    STANDARD_FIELDS
    + [_PRICE_INCREASE_VARIANTS[1]]   # "Price Increase $"
    + _STRATEGY_BUCKET_EXACT
)


# ── SVC-401: Full set present — no missing, no warnings ───────────────────────

def test_full_column_set_no_warnings():
    """SVC-401: When all standard and strategy bucket columns are present,
    the result should have no missing fields and no warnings."""
    result = validate_columns(FULL_COLUMNS)

    assert result["missing_standard"] == []
    assert result["missing_strategy_buckets"] == []
    assert result["warnings"] == []


# ── SVC-402: "Price Increase $" accepted as alternative to "%" ───────────────

def test_price_increase_dollar_accepted():
    """SVC-402: 'Price Increase $' satisfies the Price Increase bucket —
    neither the canonical missing name nor any warning should appear."""
    result = validate_columns(FULL_COLUMNS_DOLLAR)

    assert result["missing_standard"] == []
    assert result["missing_strategy_buckets"] == []
    assert result["warnings"] == []
    # Canonical placeholder must not appear in missing list
    assert _PRICE_INCREASE_CANONICAL not in result["missing_strategy_buckets"]


# ── SVC-403: All strategy buckets missing ─────────────────────────────────────

def test_all_strategy_buckets_missing():
    """SVC-403: When only standard fields are uploaded (no strategy buckets),
    all strategy bucket names should appear in missing_strategy_buckets and
    a warning about the Strategy Zone should be emitted."""
    result = validate_columns(STANDARD_FIELDS)

    # Price Increase canonical name + all exact fields
    expected_missing = [_PRICE_INCREASE_CANONICAL] + _STRATEGY_BUCKET_EXACT
    assert result["missing_strategy_buckets"] == expected_missing
    assert result["missing_standard"] == []

    assert len(result["warnings"]) == 1
    warning = result["warnings"][0]
    assert "Strategy Bucket" in warning
    assert "Strategy Zone" in warning


# ── SVC-404: Partial standard fields missing ──────────────────────────────────

def test_partial_standard_fields_missing():
    """SVC-404: Dropping a few standard fields should list them in
    missing_standard and emit a warning naming them."""
    dropped = {"Brand", "Billing State", "Employees"}
    partial = [c for c in FULL_COLUMNS if c not in dropped]

    result = validate_columns(partial)

    assert set(result["missing_standard"]) == dropped
    assert result["missing_strategy_buckets"] == []
    assert len(result["warnings"]) == 1
    warning = result["warnings"][0]
    assert "standard Salesforce fields" in warning
    for field in dropped:
        assert field in warning


# ── SVC-405: Extra columns reported ───────────────────────────────────────────

def test_extra_columns_reported():
    """SVC-405: Columns that belong to neither standard nor strategy bucket
    sets should appear in the 'extra' list and NOT trigger a warning."""
    extra_cols = ["Custom Field 1", "Salesforce Owner ID", "Weird Extra"]
    cols = FULL_COLUMNS + extra_cols

    result = validate_columns(cols)

    assert set(result["extra"]) == set(extra_cols)
    assert result["missing_standard"] == []
    assert result["missing_strategy_buckets"] == []
    # Extra columns alone do not produce warnings
    assert result["warnings"] == []


# ── SVC-406: Both standard and strategy fields missing ───────────────────────

def test_both_standard_and_strategy_missing_produces_two_warnings():
    """SVC-406: When both standard and strategy fields are missing, two
    separate warnings should be emitted."""
    # Pass only Account Name and Account Owner — stripped down
    minimal = ["Account Name", "Account Owner"]
    result = validate_columns(minimal)

    assert len(result["warnings"]) == 2
    # One warning references standard fields, one references strategy zone
    warning_text = " ".join(result["warnings"])
    assert "standard Salesforce fields" in warning_text
    assert "Strategy Zone" in warning_text


# ── SVC-407: Empty column list ────────────────────────────────────────────────

def test_empty_columns():
    """SVC-407: An empty column list should flag every standard and strategy
    bucket field as missing."""
    result = validate_columns([])

    assert set(result["missing_standard"]) == set(STANDARD_FIELDS)
    expected_strategy = [_PRICE_INCREASE_CANONICAL] + _STRATEGY_BUCKET_EXACT
    assert result["missing_strategy_buckets"] == expected_strategy
    assert result["extra"] == []
    assert len(result["warnings"]) == 2


# ── SVC-408: Price Increase "%" variant explicitly named in missing ───────────

def test_price_increase_canonical_name_in_missing_when_absent():
    """SVC-408: When neither Price Increase variant is present, the canonical
    placeholder string should appear in missing_strategy_buckets."""
    result = validate_columns(STANDARD_FIELDS)  # no strategy buckets

    assert _PRICE_INCREASE_CANONICAL in result["missing_strategy_buckets"]


# ── SVC-409: Only one extra column — no false missing reports ─────────────────

def test_single_extra_column_only():
    """SVC-409: A single unrecognized column alongside a full set should
    produce exactly that column in extra and nothing else unexpected."""
    cols = FULL_COLUMNS + ["Random Extra"]
    result = validate_columns(cols)

    assert result["extra"] == ["Random Extra"]
    assert result["missing_standard"] == []
    assert result["missing_strategy_buckets"] == []
    assert result["warnings"] == []


# ── SVC-410: Warning tone check ───────────────────────────────────────────────

def test_strategy_warning_mentions_strategy_zone():
    """SVC-410: The strategy-bucket warning should name 'Strategy Zone'
    (matching the language in system_prompt.md)."""
    result = validate_columns(STANDARD_FIELDS)
    strategy_warnings = [w for w in result["warnings"] if "Strategy Zone" in w]
    assert len(strategy_warnings) == 1


def test_standard_warning_mentions_brief_reliability():
    """SVC-410b: The standard-fields warning should mention brief reliability,
    not just list the missing names."""
    cols = [c for c in FULL_COLUMNS if c != "Brand"]
    result = validate_columns(cols)
    std_warnings = [w for w in result["warnings"] if "standard Salesforce fields" in w]
    assert len(std_warnings) == 1
    assert "reliable" in std_warnings[0]
