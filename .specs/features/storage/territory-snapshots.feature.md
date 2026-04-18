---
feature: SQLite storage for territory snapshots
domain: storage
source: db.py
tests:
  - tests/test_db.py
components:
  - db.py
design_refs: []
status: implemented
created: 2026-04-18
updated: 2026-04-18
---

# SQLite Storage for Territory Snapshots

**Purpose:** Persist every uploaded territory as a snapshot so future Phase 2+ features (delta detection, feedback loop, scheduled briefs) can build on a historical record. This is the foundation of Phase 2 — without it, no learning loop is possible.

## Design Principle Alignment

Implements vision principle #5: *"The spreadsheet is the seed, not the substrate."* State lives in our DB, not the sheet. Every upload becomes a fixed, queryable point in time.

## Feature: Territory Snapshot Storage

### Scenario: First upload initializes the database
Given no database file exists at the configured path
When the rep uploads a territory spreadsheet
Then a SQLite database file is created
And a `snapshots` table is created
And the upload is stored as snapshot #1
And the function returns the new snapshot ID and timestamp

### Scenario: Subsequent upload appends a new snapshot
Given a database with one existing snapshot
When the rep uploads a new territory spreadsheet
Then a new snapshot row is inserted
And both snapshots remain queryable
And IDs are sequential

### Scenario: Retrieve the most recent snapshot
Given a database with three snapshots saved at different times
When code calls `get_latest_snapshot()`
Then it returns the snapshot with the most recent `uploaded_at` timestamp
And the returned object includes id, uploaded_at, source_filename, row_count, column_names, and the full dataframe

### Scenario: Round-trip preserves dataframe content
Given a territory spreadsheet
When the upload is saved via `save_snapshot()` and then retrieved via `get_latest_snapshot()`
Then the retrieved DataFrame equals the original (same shape, same column names, same values)

### Scenario: List all snapshots in descending date order
Given a database with multiple snapshots
When code calls `get_snapshots()`
Then a list of snapshot summaries is returned
And the list is ordered newest first
And each entry includes id, uploaded_at, source_filename, row_count
And the full dataframe is NOT included (use `get_snapshot(id)` to fetch)

### Scenario: Empty database returns None for latest
Given an initialized database with no snapshots
When code calls `get_latest_snapshot()`
Then None is returned

### Scenario: Get snapshot by ID returns the full record
Given a database with several snapshots
When code calls `get_snapshot(snapshot_id=2)`
Then the snapshot with id=2 is returned including its dataframe

### Scenario: Unknown snapshot ID returns None
Given a database with snapshots #1 and #2
When code calls `get_snapshot(snapshot_id=999)`
Then None is returned

### Scenario: Snapshot metadata is stored correctly
Given a DataFrame with N rows and column list ["A", "B", "C"]
When the snapshot is saved
Then the persisted record has `row_count = N` and `column_names = ["A", "B", "C"]`

### Scenario: app.py persists each upload before generating the brief
Given the rep uploads a spreadsheet via the Streamlit UI
When the user clicks "Coach me"
Then the parsed DataFrame is saved as a new snapshot
And the snapshot ID and timestamp are displayed in the run details panel
And the brief is then generated as before

## UI Mockup

```
┌─────────────────────────────────────────────────────────┐
│ GTM Coach — Prototype                                   │
│ Upload a territory export. Get coached, not filtered.   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [📂 Drop your Salesforce territory export]             │
│  ✓ test_territory.xlsx                                  │
│                                                         │
│  Anything else the coach should know?                   │
│  [____________________________________________]         │
│                                                         │
│  [ Coach me ]                                           │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ (coaching brief streams here)                           │
│                                                         │
│ ▼ Run details                                           │
│   Snapshot ID: 4                                        │
│   Saved at: 2026-04-18T14:23:07                         │
│   Input tokens: ...                                     │
│   Cache read: ...                                       │
│   Output tokens: ...                                    │
└─────────────────────────────────────────────────────────┘
```

The storage is invisible to the rep. The only UI change is `Snapshot ID` + `Saved at` added to the run details panel — confirmation that the upload was persisted for future delta detection.

## Schema

```sql
CREATE TABLE IF NOT EXISTS snapshots (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  uploaded_at     TEXT NOT NULL,         -- ISO 8601 timestamp
  source_filename TEXT,                  -- e.g. "test_territory.xlsx"
  row_count       INTEGER NOT NULL,
  column_names    TEXT NOT NULL,         -- JSON array of column names
  raw_data        TEXT NOT NULL          -- JSON-serialized dataframe (orient="records")
);
```

No indexes added at this stage. For ~weekly uploads from a handful of reps, the table stays small. Add indexes when query patterns demand them (likely in #12 when delta detection runs comparisons).

## Out of Scope (handled in later features)

- Account-level normalization with stable IDs across uploads → feature #11
- Delta detection between snapshots → feature #12
- "What changed" section in brief → feature #13
- Upload history UI page → feature #14

## Learnings

- **pandas `read_json` with a raw string is deprecated.** Wrapping the JSON payload in `io.StringIO` before passing to `pd.read_json(orient="records")` avoids the FutureWarning and keeps the round-trip clean.
- **Venv shebangs hardcode the absolute interpreter path.** Renaming a project folder after `python -m venv .venv` breaks the venv silently — every script in `.venv/bin/` becomes a broken interpreter. Either rename before creating the venv, or `rm -rf .venv && python3 -m venv .venv` after the rename. Worth flagging in setup docs.
- **The "throwaway shell" principle held up.** Wiring storage into [app.py](../../../app.py) was a 3-line diff: one import, one call, two display lines in the run-details expander. Streamlit's structure didn't fight us. Validates the design principle that UI is the cheap part to swap.
- **`init_db` inside every read function is fine at this scale.** Keeps the API simple (no separate setup step required by callers). If the DB ever grows enough that connection overhead matters, lazy-init via a module-level flag is a one-line change.
