"""Tests for the territory snapshot storage layer (db.py).

Test ID prefix: SVC (services).
"""

import pandas as pd
import pytest

from db import (
    init_db,
    save_snapshot,
    get_latest_snapshot,
    get_snapshots,
    get_snapshot,
)


@pytest.fixture
def db_path(tmp_path):
    """Provide a fresh, isolated DB path for each test."""
    return tmp_path / "test_storage.db"


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        [
            {"Account Name": "Acme Corp", "ARR": 100000, "Renewal Date": "2026-09-15"},
            {"Account Name": "Globex Inc", "ARR": 250000, "Renewal Date": "2027-01-20"},
            {"Account Name": "Initech LLC", "ARR": 75000, "Renewal Date": "2026-11-30"},
        ]
    )


def make_df(version: int) -> pd.DataFrame:
    """Build a 3-row df whose content varies by `version` so dedup doesn't kick in."""
    return pd.DataFrame(
        [
            {"Account Name": "Acme Corp", "ARR": 100000 + version, "Renewal Date": "2026-09-15"},
            {"Account Name": "Globex Inc", "ARR": 250000 + version, "Renewal Date": "2027-01-20"},
            {"Account Name": "Initech LLC", "ARR": 75000 + version, "Renewal Date": "2026-11-30"},
        ]
    )


# SVC-001: First upload initializes the database
def test_first_save_creates_db_file(db_path, sample_df):
    assert not db_path.exists()
    snapshot_id, uploaded_at, is_new = save_snapshot(sample_df, "test.xlsx", db_path)
    assert db_path.exists()
    assert snapshot_id == 1
    assert uploaded_at  # non-empty ISO timestamp string
    assert is_new is True


# SVC-002: Subsequent upload of DIFFERENT data appends a new snapshot
def test_subsequent_save_appends(db_path):
    id1, _, new1 = save_snapshot(make_df(1), "first.xlsx", db_path)
    id2, _, new2 = save_snapshot(make_df(2), "second.xlsx", db_path)
    assert id1 == 1 and new1 is True
    assert id2 == 2 and new2 is True

    snapshots = get_snapshots(db_path)
    assert len(snapshots) == 2


# SVC-003: get_latest_snapshot returns the most recently inserted
def test_get_latest_returns_most_recent(db_path):
    save_snapshot(make_df(1), "first.xlsx", db_path)
    save_snapshot(make_df(2), "second.xlsx", db_path)
    save_snapshot(make_df(3), "third.xlsx", db_path)

    latest = get_latest_snapshot(db_path)
    assert latest is not None
    assert latest["source_filename"] == "third.xlsx"
    assert latest["id"] == 3


# SVC-004: Round-trip preserves dataframe content
def test_roundtrip_preserves_dataframe(db_path, sample_df):
    save_snapshot(sample_df, "test.xlsx", db_path)
    latest = get_latest_snapshot(db_path)

    retrieved = latest["dataframe"]
    pd.testing.assert_frame_equal(retrieved, sample_df)


# SVC-005: get_snapshots returns descending order with summary fields only
def test_get_snapshots_descending_order_summary_only(db_path):
    save_snapshot(make_df(1), "first.xlsx", db_path)
    save_snapshot(make_df(2), "second.xlsx", db_path)
    save_snapshot(make_df(3), "third.xlsx", db_path)

    snapshots = get_snapshots(db_path)
    assert len(snapshots) == 3
    # Newest first
    assert snapshots[0]["source_filename"] == "third.xlsx"
    assert snapshots[1]["source_filename"] == "second.xlsx"
    assert snapshots[2]["source_filename"] == "first.xlsx"

    # Summary fields present
    for s in snapshots:
        assert "id" in s
        assert "uploaded_at" in s
        assert "source_filename" in s
        assert "row_count" in s
    # Full dataframe NOT included in list view
    assert "dataframe" not in snapshots[0]


# SVC-006: Empty DB returns None for latest
def test_get_latest_empty_db_returns_none(db_path):
    init_db(db_path)
    assert get_latest_snapshot(db_path) is None


# SVC-007: get_snapshot by ID returns full record with dataframe
def test_get_snapshot_by_id_returns_full_record(db_path):
    df1 = make_df(1)
    df2 = make_df(2)
    save_snapshot(df1, "first.xlsx", db_path)
    save_snapshot(df2, "second.xlsx", db_path)

    snapshot = get_snapshot(2, db_path)
    assert snapshot is not None
    assert snapshot["id"] == 2
    assert snapshot["source_filename"] == "second.xlsx"
    assert "dataframe" in snapshot
    pd.testing.assert_frame_equal(snapshot["dataframe"], df2)


# SVC-008: Unknown snapshot ID returns None
def test_get_snapshot_unknown_id_returns_none(db_path, sample_df):
    save_snapshot(sample_df, "first.xlsx", db_path)
    assert get_snapshot(999, db_path) is None


# SVC-009: row_count and column_names stored correctly
def test_snapshot_metadata_correct(db_path, sample_df):
    save_snapshot(sample_df, "test.xlsx", db_path)
    latest = get_latest_snapshot(db_path)
    assert latest["row_count"] == 3
    assert latest["column_names"] == ["Account Name", "ARR", "Renewal Date"]


# SVC-010: Empty get_snapshots on initialized but empty DB
def test_get_snapshots_empty_db_returns_empty_list(db_path):
    init_db(db_path)
    assert get_snapshots(db_path) == []


# SVC-011: Identical re-upload dedups (returns existing ID, is_new=False)
def test_duplicate_upload_dedups(db_path, sample_df):
    id1, ts1, new1 = save_snapshot(sample_df, "first.xlsx", db_path)
    id2, ts2, new2 = save_snapshot(sample_df, "second.xlsx", db_path)

    assert id1 == 1 and new1 is True
    assert id2 == 1 and new2 is False  # same ID returned, not a new snapshot
    assert ts2 == ts1  # original timestamp preserved

    snapshots = get_snapshots(db_path)
    assert len(snapshots) == 1  # only one snapshot exists


# SVC-012: Dedup only checks against the LATEST snapshot, not all history
def test_dedup_only_against_latest(db_path):
    df_a = make_df(1)
    df_b = make_df(2)
    save_snapshot(df_a, "a.xlsx", db_path)
    save_snapshot(df_b, "b.xlsx", db_path)
    # Re-uploading df_a now (which matches snapshot #1 but NOT the latest #2) should create #3
    id3, _, new3 = save_snapshot(df_a, "a-again.xlsx", db_path)
    assert id3 == 3
    assert new3 is True
    assert len(get_snapshots(db_path)) == 3
