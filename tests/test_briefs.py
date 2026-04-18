"""Tests for brief persistence (db.py: save_brief, get_briefs, get_brief).

Test ID prefix: SVC-5xx (services, briefs domain).
"""

import pandas as pd
import pytest

from db import save_snapshot, save_brief, get_briefs, get_brief


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_briefs.db"


@pytest.fixture
def snapshot_id(db_path):
    df = pd.DataFrame(
        [{"CR Customer ID": "CR-1", "Account Name": "Acme", "ARR": 100000}]
    )
    sid, _, _ = save_snapshot(df, "test.xlsx", db_path)
    return sid


# SVC-501: First save_brief returns id=1 and ISO timestamp
def test_first_save_brief_returns_id_and_timestamp(db_path, snapshot_id):
    bid, generated_at = save_brief(snapshot_id, "the brief text", db_path=db_path)
    assert bid == 1
    assert generated_at  # non-empty ISO timestamp


# SVC-502: Sequential briefs get sequential IDs
def test_sequential_briefs_appended(db_path, snapshot_id):
    bid1, _ = save_brief(snapshot_id, "first brief", db_path=db_path)
    bid2, _ = save_brief(snapshot_id, "second brief", db_path=db_path)
    assert bid1 == 1
    assert bid2 == 2


# SVC-503: get_briefs returns newest first, no brief_text payload
def test_get_briefs_descending_no_text(db_path, snapshot_id):
    save_brief(snapshot_id, "first brief", db_path=db_path)
    save_brief(snapshot_id, "second brief", db_path=db_path)
    save_brief(snapshot_id, "third brief", db_path=db_path)

    briefs = get_briefs(db_path)
    assert len(briefs) == 3
    # Newest first
    assert briefs[0]["id"] == 3
    assert briefs[2]["id"] == 1
    # No full text in list view
    for b in briefs:
        assert "brief_text" not in b
        assert "id" in b
        assert "snapshot_id" in b
        assert "generated_at" in b


# SVC-504: get_brief returns full record including brief_text
def test_get_brief_by_id_returns_full_text(db_path, snapshot_id):
    save_brief(snapshot_id, "first brief", db_path=db_path)
    save_brief(snapshot_id, "second brief text content", db_path=db_path)

    brief = get_brief(2, db_path)
    assert brief is not None
    assert brief["id"] == 2
    assert brief["brief_text"] == "second brief text content"


# SVC-505: Unknown brief_id returns None
def test_get_brief_unknown_id_returns_none(db_path, snapshot_id):
    save_brief(snapshot_id, "first", db_path=db_path)
    assert get_brief(999, db_path) is None


# SVC-506: Optional metadata fields persist when provided
def test_brief_metadata_persists(db_path, snapshot_id):
    save_brief(
        snapshot_id,
        "the brief",
        rep_context="worried about Globex",
        model="claude-sonnet-4-6",
        input_tokens=12345,
        output_tokens=2345,
        cache_read_tokens=10000,
        db_path=db_path,
    )
    brief = get_brief(1, db_path)
    assert brief["rep_context"] == "worried about Globex"
    assert brief["model"] == "claude-sonnet-4-6"
    assert brief["input_tokens"] == 12345
    assert brief["output_tokens"] == 2345
    assert brief["cache_read_tokens"] == 10000


# SVC-507: Optional metadata fields default to None when omitted
def test_brief_metadata_optional(db_path, snapshot_id):
    save_brief(snapshot_id, "the brief", db_path=db_path)
    brief = get_brief(1, db_path)
    assert brief["rep_context"] is None
    assert brief["model"] is None
    assert brief["input_tokens"] is None


# SVC-508: Briefs are linked to their source snapshot
def test_briefs_link_to_snapshot(db_path, snapshot_id):
    save_brief(snapshot_id, "linked brief", db_path=db_path)
    brief = get_brief(1, db_path)
    assert brief["snapshot_id"] == snapshot_id


# SVC-509: Empty briefs list on fresh DB
def test_get_briefs_empty_db(db_path):
    # No snapshot needed — get_briefs auto-inits
    assert get_briefs(db_path) == []
