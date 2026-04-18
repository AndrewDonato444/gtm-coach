"""Tests for account-level normalization (db.py).

Test ID prefix: SVC (services).
"""

import pandas as pd
import pytest

from db import (
    _normalize_account_id,
    save_snapshot,
    get_account_history,
    get_accounts_in_snapshot,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_storage.db"


# ----- Normalization helper -----

# SVC-101: CR Customer ID becomes cr:{id}
def test_normalize_uses_cr_customer_id():
    row = {"CR Customer ID": "CR-10023", "Account Name": "Whatever"}
    assert _normalize_account_id(row) == "cr:CR-10023"


# SVC-102: Falls back to slugified Account Name when CR ID missing
def test_normalize_falls_back_to_slugified_name():
    row = {"Account Name": "Morrison Logistics Group"}
    assert _normalize_account_id(row) == "name:morrison-logistics-group"


# SVC-103: CR ID wins over name when both present
def test_normalize_cr_id_wins_over_name():
    row = {"CR Customer ID": "CR-10023", "Account Name": "Morrison Logistics Group"}
    assert _normalize_account_id(row) == "cr:CR-10023"


# SVC-104: Blank CR ID falls through to name
def test_normalize_blank_cr_id_falls_through():
    row = {"CR Customer ID": "", "Account Name": "Acme Corp"}
    assert _normalize_account_id(row) == "name:acme-corp"


# SVC-105: Whitespace-only CR ID falls through to name
def test_normalize_whitespace_cr_id_falls_through():
    row = {"CR Customer ID": "   ", "Account Name": "Acme Corp"}
    assert _normalize_account_id(row) == "name:acme-corp"


# SVC-106: Both missing raises ValueError
def test_normalize_both_missing_raises():
    row = {"Other Column": "irrelevant"}
    with pytest.raises(ValueError):
        _normalize_account_id(row)


# SVC-107: Both blank raises ValueError
def test_normalize_both_blank_raises():
    row = {"CR Customer ID": "", "Account Name": ""}
    with pytest.raises(ValueError):
        _normalize_account_id(row)


# SVC-108: Special characters slugify cleanly
def test_normalize_special_chars_slugify():
    row = {"Account Name": "Smith & Wesson, Inc."}
    assert _normalize_account_id(row) == "name:smith-wesson-inc"


# SVC-109: Multiple consecutive separators collapse
def test_normalize_collapses_consecutive_separators():
    row = {"Account Name": "Foo  --  Bar  &  Baz"}
    # Whatever the exact slug, no double-dashes and no leading/trailing dash
    result = _normalize_account_id(row)
    assert result.startswith("name:")
    slug = result.split(":", 1)[1]
    assert "--" not in slug
    assert not slug.startswith("-")
    assert not slug.endswith("-")


# ----- Persistence -----

# SVC-110: save_snapshot populates account_rows
def test_save_snapshot_populates_account_rows(db_path):
    df = pd.DataFrame(
        [
            {"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 100000},
            {"CR Customer ID": "CR-10024", "Account Name": "Globex", "ARR": 250000},
            {"CR Customer ID": "CR-10025", "Account Name": "Initech", "ARR": 75000},
        ]
    )
    snapshot_id, _, _ = save_snapshot(df, "test.xlsx", db_path)

    accounts = get_accounts_in_snapshot(snapshot_id, db_path)
    assert len(accounts) == 3
    account_ids = {a["account_id"] for a in accounts}
    assert account_ids == {"cr:CR-10023", "cr:CR-10024", "cr:CR-10025"}


# SVC-111: account_rows preserves snapshot relationship across uploads
def test_account_history_across_snapshots(db_path):
    df1 = pd.DataFrame(
        [{"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 100000}]
    )
    df2 = pd.DataFrame(
        [{"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 110000}]
    )
    save_snapshot(df1, "monday.xlsx", db_path)
    save_snapshot(df2, "next-monday.xlsx", db_path)

    history = get_account_history("cr:CR-10023", db_path)
    assert len(history) == 2
    # Oldest first
    assert history[0]["row_data"]["ARR"] == 100000
    assert history[1]["row_data"]["ARR"] == 110000


# SVC-112: get_account_history returns ordered list with metadata
def test_get_account_history_includes_snapshot_metadata(db_path):
    # Vary the ARR each upload so dedup doesn't collapse them
    save_snapshot(
        pd.DataFrame([{"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 100000}]),
        "first.xlsx", db_path,
    )
    save_snapshot(
        pd.DataFrame([{"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 100001}]),
        "second.xlsx", db_path,
    )
    save_snapshot(
        pd.DataFrame([{"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 100002}]),
        "third.xlsx", db_path,
    )

    history = get_account_history("cr:CR-10023", db_path)
    assert len(history) == 3
    for entry in history:
        assert "snapshot_id" in entry
        assert "uploaded_at" in entry
        assert "row_data" in entry
    # Ordered by snapshot_id ascending (which mirrors uploaded_at ascending)
    snapshot_ids = [e["snapshot_id"] for e in history]
    assert snapshot_ids == sorted(snapshot_ids)


# SVC-113: get_accounts_in_snapshot returns all rows for one snapshot
def test_get_accounts_in_snapshot(db_path):
    df = pd.DataFrame(
        [{"CR Customer ID": f"CR-{i}", "Account Name": f"Co{i}", "ARR": i * 1000} for i in range(50)]
    )
    snapshot_id, _, _ = save_snapshot(df, "big.xlsx", db_path)

    accounts = get_accounts_in_snapshot(snapshot_id, db_path)
    assert len(accounts) == 50
    for a in accounts:
        assert "account_id" in a
        assert "account_name" in a
        assert "row_data" in a


# SVC-114: Unknown account_id returns empty history
def test_unknown_account_id_returns_empty_history(db_path):
    df = pd.DataFrame(
        [{"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 100000}]
    )
    save_snapshot(df, "test.xlsx", db_path)

    assert get_account_history("cr:NEVER-SEEN", db_path) == []


# SVC-115: Mixed-strategy snapshot (some CR IDs, some name fallbacks)
def test_mixed_id_strategies_in_snapshot(db_path):
    df = pd.DataFrame(
        [
            {"CR Customer ID": "CR-10023", "Account Name": "Acme", "ARR": 100000},
            {"CR Customer ID": "", "Account Name": "Globex", "ARR": 250000},
        ]
    )
    snapshot_id, _, _ = save_snapshot(df, "mixed.xlsx", db_path)

    accounts = get_accounts_in_snapshot(snapshot_id, db_path)
    account_ids = {a["account_id"] for a in accounts}
    assert account_ids == {"cr:CR-10023", "name:globex"}


# SVC-116: Account name preserved as raw display value
def test_account_name_preserved_for_display(db_path):
    df = pd.DataFrame(
        [{"CR Customer ID": "CR-10023", "Account Name": "Morrison Logistics Group", "ARR": 412000}]
    )
    snapshot_id, _, _ = save_snapshot(df, "test.xlsx", db_path)

    accounts = get_accounts_in_snapshot(snapshot_id, db_path)
    assert accounts[0]["account_name"] == "Morrison Logistics Group"
