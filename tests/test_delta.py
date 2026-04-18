"""Tests for week-over-week delta detection (delta.py).

Test ID prefix: SVC-2xx (services, delta feature block).
Fixtures use tmp_path to keep each test isolated.
"""

import pandas as pd
import pytest

from db import save_snapshot
from delta import compute_delta, compute_latest_delta, format_delta_for_brief, COACHING_FIELDS


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_storage.db"


def _make_account(cr_id: str, name: str, **fields) -> dict:
    """Build a minimal account row dict for DataFrame construction."""
    return {"CR Customer ID": cr_id, "Account Name": name, **fields}


def _save_df(rows: list[dict], filename: str, db_path) -> int:
    df = pd.DataFrame(rows)
    snapshot_id, _, _ = save_snapshot(df, filename, db_path)
    return snapshot_id


# ----- compute_delta: basic structure -----

# SVC-201: Returns the expected top-level keys
def test_compute_delta_returns_expected_keys(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme")],
        "week1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme")],
        "week2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert "latest_snapshot_id" in delta
    assert "previous_snapshot_id" in delta
    assert "new_accounts" in delta
    assert "dropped_accounts" in delta
    assert "changed_accounts" in delta


# SVC-202: Snapshot IDs round-trip correctly in the output
def test_compute_delta_records_snapshot_ids(db_path):
    snap1 = _save_df([_make_account("CR-001", "Acme")], "w1.xlsx", db_path)
    snap2 = _save_df([_make_account("CR-001", "Acme")], "w2.xlsx", db_path)
    delta = compute_delta(snap2, snap1, db_path)

    assert delta["latest_snapshot_id"] == snap2
    assert delta["previous_snapshot_id"] == snap1


# ----- new_accounts -----

# SVC-203: Account in latest but not previous shows up in new_accounts
def test_new_account_detected(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme")],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [
            _make_account("CR-001", "Acme"),
            _make_account("CR-002", "Globex"),  # new
        ],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["new_accounts"]) == 1
    assert delta["new_accounts"][0]["account_id"] == "cr:CR-002"
    assert delta["dropped_accounts"] == []


# SVC-204: new_accounts entry includes account_id, account_name, row_data
def test_new_account_entry_shape(db_path):
    snap1 = _save_df([], "empty.xlsx", db_path)
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"Price Increase %": "5%"})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    entry = delta["new_accounts"][0]
    assert "account_id" in entry
    assert "account_name" in entry
    assert "row_data" in entry
    assert entry["account_name"] == "Acme"


# ----- dropped_accounts -----

# SVC-205: Account in previous but not latest shows up in dropped_accounts
def test_dropped_account_detected(db_path):
    snap1 = _save_df(
        [
            _make_account("CR-001", "Acme"),
            _make_account("CR-002", "Globex"),  # will be dropped
        ],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme")],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["dropped_accounts"]) == 1
    assert delta["dropped_accounts"][0]["account_id"] == "cr:CR-002"
    assert delta["new_accounts"] == []


# ----- changed_accounts -----

# SVC-206: Coaching field change detected correctly
def test_coaching_field_change_detected(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme", **{"Open Opp?": "No"})],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"Open Opp?": "Yes"})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["changed_accounts"]) == 1
    changed = delta["changed_accounts"][0]
    assert changed["account_id"] == "cr:CR-001"
    assert "Open Opp?" in changed["changes"]
    assert changed["changes"]["Open Opp?"]["before"] == "No"
    assert changed["changes"]["Open Opp?"]["after"] == "Yes"


# SVC-207: Multiple coaching fields changed in same account
def test_multiple_coaching_fields_changed(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme", **{
            "Price Increase %": "0%",
            "Assurance": "No",
            "Travel": "No",
        })],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{
            "Price Increase %": "8%",
            "Assurance": "Yes",
            "Travel": "No",  # unchanged
        })],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["changed_accounts"]) == 1
    changes = delta["changed_accounts"][0]["changes"]
    assert "Price Increase %" in changes
    assert "Assurance" in changes
    assert "Travel" not in changes  # unchanged, should be absent


# SVC-208: Non-coaching field change does NOT appear in changed_accounts
def test_non_coaching_field_change_ignored(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme", **{"Billing City": "Chicago"})],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"Billing City": "New York"})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert delta["changed_accounts"] == []


# SVC-209: Account with no coaching field changes not in changed_accounts
def test_unchanged_account_not_in_changed(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme", **{"Open Opp?": "Yes", "Assurance": "No"})],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"Open Opp?": "Yes", "Assurance": "No"})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert delta["changed_accounts"] == []
    assert delta["new_accounts"] == []
    assert delta["dropped_accounts"] == []


# SVC-210: Customer Renewal Date tracked as coaching-relevant change
def test_customer_renewal_date_change_detected(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme", **{"Customer Renewal Date": "2026-06-01"})],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"Customer Renewal Date": "2026-09-01"})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["changed_accounts"]) == 1
    assert "Customer Renewal Date" in delta["changed_accounts"][0]["changes"]


# SVC-211: ESA Consultant change detected
def test_esa_consultant_change_detected(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme", **{"ESA Consultant": "Jane Smith"})],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"ESA Consultant": "Bob Jones"})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["changed_accounts"]) == 1
    assert "ESA Consultant" in delta["changed_accounts"][0]["changes"]


# SVC-212: None and empty string treated as equivalent (no spurious change)
def test_none_and_empty_string_treated_as_equivalent(db_path):
    # One snapshot has field absent (None), other has field as "" — should not flag
    snap1 = _save_df(
        [_make_account("CR-001", "Acme")],  # Notes field absent → None
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"Notes": ""})],  # Notes is empty string
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert delta["changed_accounts"] == []


# SVC-213: Whitespace-only values treated as empty (no spurious change)
def test_whitespace_treated_as_empty(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme", **{"Notes": "   "})],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme", **{"Notes": ""})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert delta["changed_accounts"] == []


# SVC-214: changed_accounts entry includes account_id and account_name
def test_changed_account_entry_shape(db_path):
    snap1 = _save_df(
        [_make_account("CR-001", "Acme Corp", **{"Invoice": "No"})],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [_make_account("CR-001", "Acme Corp", **{"Invoice": "Yes"})],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    entry = delta["changed_accounts"][0]
    assert entry["account_id"] == "cr:CR-001"
    assert entry["account_name"] == "Acme Corp"
    assert "changes" in entry


# SVC-215: Mixed scenario — new, dropped, and changed in one delta
def test_mixed_delta_scenario(db_path):
    snap1 = _save_df(
        [
            _make_account("CR-001", "Acme", **{"Open Opp?": "No"}),
            _make_account("CR-002", "Globex"),   # will be dropped
        ],
        "w1.xlsx",
        db_path,
    )
    snap2 = _save_df(
        [
            _make_account("CR-001", "Acme", **{"Open Opp?": "Yes"}),  # changed
            _make_account("CR-003", "Initech"),  # new
        ],
        "w2.xlsx",
        db_path,
    )
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["new_accounts"]) == 1
    assert delta["new_accounts"][0]["account_id"] == "cr:CR-003"
    assert len(delta["dropped_accounts"]) == 1
    assert delta["dropped_accounts"][0]["account_id"] == "cr:CR-002"
    assert len(delta["changed_accounts"]) == 1
    assert delta["changed_accounts"][0]["account_id"] == "cr:CR-001"


# SVC-216: Empty snapshots produce empty delta lists
def test_both_snapshots_empty(db_path):
    snap1 = _save_df([], "empty1.xlsx", db_path)
    snap2 = _save_df([], "empty2.xlsx", db_path)
    delta = compute_delta(snap2, snap1, db_path)

    assert delta["new_accounts"] == []
    assert delta["dropped_accounts"] == []
    assert delta["changed_accounts"] == []


# ----- compute_latest_delta -----

# SVC-217: Returns None when fewer than 2 snapshots exist
def test_compute_latest_delta_returns_none_with_no_snapshots(db_path):
    result = compute_latest_delta(db_path)
    assert result is None


# SVC-218: Returns None with exactly one snapshot
def test_compute_latest_delta_returns_none_with_one_snapshot(db_path):
    _save_df([_make_account("CR-001", "Acme")], "only.xlsx", db_path)
    result = compute_latest_delta(db_path)
    assert result is None


# SVC-219: Auto-selects the two most recent snapshots
def test_compute_latest_delta_uses_two_most_recent(db_path):
    # All three snapshots must have distinct content — dedup would collapse identical ones.
    snap1 = _save_df([_make_account("CR-001", "Acme", **{"Payments": "No"})], "w1.xlsx", db_path)
    snap2 = _save_df([_make_account("CR-001", "Acme", **{"Payments": "Yes"})], "w2.xlsx", db_path)
    snap3 = _save_df([_make_account("CR-001", "Acme", **{"Payments": "Yes", "Notes": "added later"})], "w3.xlsx", db_path)

    delta = compute_latest_delta(db_path)

    # Should compare snap3 (latest) vs snap2 (previous), not snap1
    assert delta["latest_snapshot_id"] == snap3
    assert delta["previous_snapshot_id"] == snap2


# SVC-220: compute_latest_delta returns full delta shape
def test_compute_latest_delta_returns_full_shape(db_path):
    _save_df([_make_account("CR-001", "Acme")], "w1.xlsx", db_path)
    _save_df([_make_account("CR-001", "Acme"), _make_account("CR-002", "Globex")], "w2.xlsx", db_path)

    delta = compute_latest_delta(db_path)

    assert delta is not None
    assert len(delta["new_accounts"]) == 1
    assert delta["new_accounts"][0]["account_id"] == "cr:CR-002"


# SVC-221: All COACHING_FIELDS are tracked (coverage check)
def test_all_coaching_fields_are_checked(db_path):
    """Verify every field in COACHING_FIELDS can be detected as a change."""
    before_row = _make_account("CR-001", "Acme", **{f: "before" for f in COACHING_FIELDS})
    after_row = _make_account("CR-001", "Acme", **{f: "after" for f in COACHING_FIELDS})

    snap1 = _save_df([before_row], "w1.xlsx", db_path)
    snap2 = _save_df([after_row], "w2.xlsx", db_path)
    delta = compute_delta(snap2, snap1, db_path)

    assert len(delta["changed_accounts"]) == 1
    detected_fields = set(delta["changed_accounts"][0]["changes"].keys())
    assert detected_fields == set(COACHING_FIELDS)


# ----- format_delta_for_brief -----

# SVC-222: No-change delta returns empty string
def test_format_delta_empty_when_no_changes():
    delta = {
        "latest_snapshot_id": 2,
        "previous_snapshot_id": 1,
        "new_accounts": [],
        "dropped_accounts": [],
        "changed_accounts": [],
    }
    result = format_delta_for_brief(delta)
    assert result == ""


# SVC-223: New accounts only — section includes account name and key fields
def test_format_delta_new_accounts_only():
    delta = {
        "latest_snapshot_id": 2,
        "previous_snapshot_id": 1,
        "new_accounts": [
            {
                "account_id": "cr:CR-001",
                "account_name": "Initech Corp",
                "row_data": {"Customer Renewal Date": "2026-09-01", "Price Increase %": "8%"},
            }
        ],
        "dropped_accounts": [],
        "changed_accounts": [],
    }
    result = format_delta_for_brief(delta)
    assert result != ""
    assert "What Changed Since Last Upload" in result
    assert "NEW this week" in result
    assert "Initech Corp" in result
    assert "2026-09-01" in result
    assert "8%" in result
    assert "DROPPED" not in result
    assert "CHANGED" not in result


# SVC-224: Dropped accounts only — section lists account names
def test_format_delta_dropped_accounts_only():
    delta = {
        "latest_snapshot_id": 2,
        "previous_snapshot_id": 1,
        "new_accounts": [],
        "dropped_accounts": [
            {
                "account_id": "cr:CR-002",
                "account_name": "Morrison Logistics",
                "row_data": {},
            }
        ],
        "changed_accounts": [],
    }
    result = format_delta_for_brief(delta)
    assert result != ""
    assert "DROPPED this week" in result
    assert "Morrison Logistics" in result
    assert "NEW" not in result


# SVC-225: Changed accounts — shows field, before, and after values
def test_format_delta_changed_accounts_shows_field_diff():
    delta = {
        "latest_snapshot_id": 2,
        "previous_snapshot_id": 1,
        "new_accounts": [],
        "dropped_accounts": [],
        "changed_accounts": [
            {
                "account_id": "cr:CR-001",
                "account_name": "Acme",
                "changes": {
                    "Open Opp?": {"before": "No", "after": "Yes"},
                },
            }
        ],
    }
    result = format_delta_for_brief(delta)
    assert result != ""
    assert "CHANGED" in result
    assert "Acme" in result
    assert "Open Opp?" in result
    assert "No" in result
    assert "Yes" in result


# SVC-226: All three change types combined — each section present
def test_format_delta_all_change_types_combined():
    delta = {
        "latest_snapshot_id": 3,
        "previous_snapshot_id": 2,
        "new_accounts": [
            {"account_id": "cr:CR-003", "account_name": "Pinnacle", "row_data": {}},
        ],
        "dropped_accounts": [
            {"account_id": "cr:CR-002", "account_name": "Globex", "row_data": {}},
        ],
        "changed_accounts": [
            {
                "account_id": "cr:CR-001",
                "account_name": "Acme",
                "changes": {
                    "Price Increase %": {"before": "0%", "after": "8%"},
                    "Assurance": {"before": "No", "after": "Yes"},
                },
            }
        ],
    }
    result = format_delta_for_brief(delta)
    assert "What Changed Since Last Upload" in result
    assert "NEW this week (1)" in result
    assert "Pinnacle" in result
    assert "DROPPED this week (1)" in result
    assert "Globex" in result
    assert "CHANGED (1 accounts)" in result
    assert "Acme" in result
    assert "Price Increase %" in result
    assert "Assurance" in result
