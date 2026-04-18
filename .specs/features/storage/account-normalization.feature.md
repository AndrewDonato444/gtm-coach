---
feature: Account-level normalization (stable IDs across uploads)
domain: storage
source: db.py
tests:
  - tests/test_db.py
  - tests/test_normalization.py
components:
  - db.py
design_refs: []
status: implemented
created: 2026-04-18
updated: 2026-04-18
---

# Account-Level Normalization

**Purpose:** Identify the same account across multiple territory uploads so that downstream features (#12 delta detection, #13 "what changed" in brief, #21 brief rating per-account) can ask questions like *"how has Acme changed week over week?"* Without this, every snapshot is an opaque blob.

## Design Principle Alignment

Implements vision principle #5 (*spreadsheet is the seed, not the substrate*) by building queryable account-level structure on top of the raw snapshots from #10.

## ID Strategy

Two-tier with explicit prefixing so the source is always recoverable:

1. **`cr:{id}`** — preferred. Uses the `CR Customer ID` column from the SF export (e.g. `cr:CR-10023`). Authoritative because it's Salesforce's own identifier.
2. **`name:{slug}`** — fallback. Slugified `Account Name` when CR ID is missing or blank (e.g. `name:morrison-logistics-group`). Less reliable (rename = new ID) but better than nothing.
3. **Raises** if both are missing — there's no honest way to track an account with neither identifier.

The prefix tells future code which strategy was used. If the rep ever has accounts that switch from name-based to CR-based (e.g. they backfill the column), we can write a migration that knows what it's looking at.

## Schema Addition

```sql
CREATE TABLE IF NOT EXISTS account_rows (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id   INTEGER NOT NULL REFERENCES snapshots(id),
  account_id    TEXT NOT NULL,    -- e.g. "cr:CR-10023" or "name:acme-corp"
  account_name  TEXT,             -- raw display name for debugging
  row_data      TEXT NOT NULL     -- JSON of the single row
);
CREATE INDEX IF NOT EXISTS idx_account_rows_account  ON account_rows(account_id);
CREATE INDEX IF NOT EXISTS idx_account_rows_snapshot ON account_rows(snapshot_id);
```

`snapshots.raw_data` stays in place — it's the source of truth for the full dataframe and existing #10 functions still depend on it. `account_rows` is the *queryable* view on top.

## Feature: Account Normalization

### Scenario: Account ID derived from CR Customer ID
Given a row with `CR Customer ID = "CR-10023"`
When `_normalize_account_id(row)` is called
Then it returns `"cr:CR-10023"`

### Scenario: Account ID falls back to slugified name
Given a row with `Account Name = "Morrison Logistics Group"` and no CR Customer ID
When `_normalize_account_id(row)` is called
Then it returns `"name:morrison-logistics-group"`

### Scenario: CR Customer ID wins over Account Name
Given a row with both `CR Customer ID = "CR-10023"` and `Account Name = "Morrison Logistics Group"`
When `_normalize_account_id(row)` is called
Then it returns `"cr:CR-10023"` (CR ID is authoritative)

### Scenario: Blank CR Customer ID falls through to Account Name
Given a row with `CR Customer ID = ""` and `Account Name = "Acme Corp"`
When `_normalize_account_id(row)` is called
Then it returns `"name:acme-corp"`

### Scenario: Both identifiers missing raises an error
Given a row with no CR Customer ID and no Account Name
When `_normalize_account_id(row)` is called
Then a ValueError is raised

### Scenario: Account name with special characters slugifies cleanly
Given a row with `Account Name = "Smith & Wesson, Inc."`
When `_normalize_account_id(row)` is called
Then it returns `"name:smith-wesson-inc"` (no consecutive dashes, no trailing dash)

## Feature: Account Row Persistence

### Scenario: save_snapshot populates account_rows
Given a DataFrame with 3 rows, each with a CR Customer ID
When `save_snapshot(df, "test.xlsx")` is called
Then 3 rows are inserted into `account_rows`
And each row's `snapshot_id` matches the new snapshot's id
And each row's `account_id` matches the CR ID strategy
And each row's `row_data` is the JSON of that single account

### Scenario: account_rows preserves snapshot relationship across uploads
Given snapshot #1 is saved with 3 accounts
And snapshot #2 is saved with the same 3 accounts (one updated)
When `account_rows` is queried for `account_id = "cr:CR-10023"`
Then 2 rows are returned (one per snapshot)

### Scenario: get_account_history returns chronological list for an account
Given an account appears in snapshots #1, #2, and #3
When `get_account_history("cr:CR-10023")` is called
Then a list of 3 entries is returned
And the list is ordered oldest first
And each entry includes snapshot_id, uploaded_at, and row_data

### Scenario: get_accounts_in_snapshot returns all rows for one snapshot
Given snapshot #5 has 50 accounts
When `get_accounts_in_snapshot(snapshot_id=5)` is called
Then a list of 50 entries is returned
And each entry includes account_id, account_name, and row_data

### Scenario: Unknown account ID returns empty history
Given no rows exist for `account_id = "cr:NEVER-SEEN"`
When `get_account_history("cr:NEVER-SEEN")` is called
Then an empty list is returned

## UI Mockup

No UI changes for this feature — it's pure data layer infrastructure. The next feature (#12 delta detection) will surface this work in the brief output.

## Out of Scope

- Detecting account renames (when `name:foo-corp` becomes `cr:FOO-123` because the rep finally backfilled the CR ID) → future cleanup, low priority until it actually happens
- Column-name flexibility (handling exports that use `Account ID` instead of `CR Customer ID`) → defer until we see a real export that needs it
- Backfilling `account_rows` for snapshots saved before this feature shipped → migration script if/when we have pre-#11 data we care about (we don't yet)

## Learnings

- **Prefixed IDs (`cr:` / `name:`) cost almost nothing and pay back forever.** A future migration that re-keys `name:foo-corp` rows to `cr:CR-12345` (because the rep finally backfilled CR IDs) becomes a clean, auditable script instead of guesswork. The 3 extra characters per ID beat the alternative.
- **Skipping un-normalizable rows beats raising at save time.** A single bad row shouldn't kill a 200-row upload. `raw_data` still preserves the skipped rows for inspection; `account_rows` just can't track them through deltas — which is honest, since they have no stable identifier.
- **Keep `raw_data` even after `account_rows` exists.** Don't refactor away the duplication. `get_latest_snapshot()['dataframe']` is a clean public API that callers (the brief, future history view) shouldn't have to know about the underlying split. Disk is cheap; API stability isn't.
- **`df.to_dict(orient="records")` is the cleanest row iteration.** Cleaner than `df.iterrows()` (no Series unpacking), survives JSON round-trip via `json.dumps(row_dict)`. Use it as the default pattern when persisting per-row.
