---
feature: Week-over-week delta detection
domain: storage
source: delta.py
tests:
  - tests/test_delta.py
components:
  - delta.py
design_refs: []
status: implemented
created: 2026-04-17
updated: 2026-04-17
---

# Week-over-Week Delta Detection

**Purpose:** Compare two territory snapshots and surface what actually changed — new accounts, dropped accounts, and coaching-relevant field changes. This is the data layer that enables feature #13 ("what changed since last upload" in the brief). Without it the coach has no memory; with it, the coach can say "Acme just opened an opp — here's your play."

## Design Principle Alignment

Implements vision principle #5 (*the spreadsheet is the seed, not the substrate*) and principle #1 (*coach, don't calculate*). The field filter is the key design decision: we don't report every changed cell, we report the cells that change what play the coach would recommend.

## Coaching Field Rationale

The `COACHING_FIELDS` constant in `delta.py` defines the filter:

| Field | Why it matters |
|---|---|
| `Price Increase %` | Core wedge trigger — a PI creates the value-add conversation |
| `Open Opp?` | Rep priority signal — an open opp demands immediate attention |
| `Assurance` | Whitespace expansion target |
| `Invoice` | Whitespace expansion target |
| `Travel` | Whitespace expansion target |
| `Payments` | Whitespace expansion target |
| `Notes` | Rep or leader has added context worth reviewing |
| `Customer Renewal Date` | Timing changes affect urgency and conversation sequencing |
| `ESA Consultant` | Relationship context — coach needs to know who's in the account |

Fields excluded intentionally: Billing City, ARR (contract value — too noisy week-over-week), address fields, metadata. They don't change what play to run.

## Feature: Delta Computation

### Scenario: New account appears in latest snapshot
Given snapshot A has accounts [Acme, Globex]
And snapshot B (newer) has accounts [Acme, Globex, Initech]
When `compute_delta(B, A)` is called
Then `new_accounts` contains one entry for Initech
And `dropped_accounts` is empty
And `changed_accounts` is empty

### Scenario: Account dropped from latest snapshot
Given snapshot A has accounts [Acme, Globex]
And snapshot B (newer) has only [Acme]
When `compute_delta(B, A)` is called
Then `dropped_accounts` contains one entry for Globex
And `new_accounts` is empty

### Scenario: Coaching field changes detected
Given snapshot A has Acme with `Open Opp? = "No"`
And snapshot B has Acme with `Open Opp? = "Yes"`
When `compute_delta(B, A)` is called
Then `changed_accounts` contains one entry for Acme
And the `changes` dict has key `Open Opp?`
And the value is `{before: "No", after: "Yes"}`

### Scenario: Non-coaching field changes are ignored
Given snapshot A has Acme with `Billing City = "Chicago"`
And snapshot B has Acme with `Billing City = "New York"`
When `compute_delta(B, A)` is called
Then `changed_accounts` is empty

### Scenario: None and empty string are treated as equivalent
Given snapshot A has Acme with `Notes` absent (None)
And snapshot B has Acme with `Notes = ""`
When `compute_delta(B, A)` is called
Then `changed_accounts` is empty (no spurious change flagged)

### Scenario: Multiple fields change in a single account
Given snapshot A has Acme with `Price Increase % = "0%"` and `Assurance = "No"`
And snapshot B has Acme with `Price Increase % = "8%"` and `Assurance = "Yes"` and `Travel = "No"` (same as before)
When `compute_delta(B, A)` is called
Then the changed entry for Acme has `changes` with keys `Price Increase %` and `Assurance`
And `Travel` is absent from `changes`

### Scenario: Mixed delta — new, dropped, and changed in one call
Given snapshot A has [Acme (Open Opp?=No), Globex]
And snapshot B has [Acme (Open Opp?=Yes), Initech]
When `compute_delta(B, A)` is called
Then `new_accounts` = [Initech]
And `dropped_accounts` = [Globex]
And `changed_accounts` = [Acme with Open Opp? change]

## Feature: Convenience Helper — compute_latest_delta

### Scenario: Returns None when fewer than 2 snapshots exist
Given the database has 0 or 1 snapshots
When `compute_latest_delta()` is called
Then it returns None

### Scenario: Auto-selects the two most recent snapshots
Given three snapshots exist (oldest=1, middle=2, newest=3)
When `compute_latest_delta()` is called
Then it compares snapshot 3 (latest) against snapshot 2 (previous)
And snapshot 1 is not involved

### Scenario: Returns full delta shape
Given two or more snapshots exist
When `compute_latest_delta()` is called
Then it returns a dict with the same shape as `compute_delta()`:
  latest_snapshot_id, previous_snapshot_id, new_accounts, dropped_accounts, changed_accounts

## Output Schema

```python
{
  "latest_snapshot_id":   int,
  "previous_snapshot_id": int,
  "new_accounts": [
    # entries from get_accounts_in_snapshot — same shape
    {"account_id": str, "account_name": str, "row_data": dict}
  ],
  "dropped_accounts": [
    {"account_id": str, "account_name": str, "row_data": dict}
  ],
  "changed_accounts": [
    {
      "account_id":   str,
      "account_name": str,
      "changes": {
        "Field Name": {"before": <original_value>, "after": <new_value>}
      }
    }
  ]
}
```

`new_accounts` and `dropped_accounts` entries are the raw dicts from `get_accounts_in_snapshot()`, so callers get the full `row_data` without an extra lookup.

## UI Mockup

No new UI for this feature alone. Feature #13 surfaces the delta in the brief. The output lands in the coaching brief as a prose section, not a table.

```
┌─────────────────────────────────────────────────────────┐
│ GTM Coach — Brief                                       │
│                                                         │
│  --- What Changed Since Last Upload ---                 │
│                                                         │
│  NEW this week (2):                                     │
│    • Initech Corp — renewal in 60 days, no open opp     │
│    • Pinnacle Systems — PI flagged at 8%                │
│                                                         │
│  DROPPED this week (1):                                 │
│    • Morrison Logistics (removed from territory?)       │
│                                                         │
│  CHANGED (3 accounts):                                  │
│    • Acme — Open Opp flipped to Yes                     │
│    • Globex — Renewal date moved from Jun → Sep         │
│    • Pinnacle — ESA Consultant changed                  │
│                                                         │
│  ... (rest of brief) ...                                │
└─────────────────────────────────────────────────────────┘
```

The brief rendering is feature #13's job. This feature just supplies the raw delta dict.

## Algorithm Notes

1. Load both snapshots via `get_accounts_in_snapshot()` — no direct SQL.
2. Build `{account_id: row}` dicts for set math.
3. New = `latest_ids - previous_ids`, dropped = `previous_ids - latest_ids`.
4. Changed = intersection, then for each account compare only `COACHING_FIELDS`.
5. Normalization: coerce to `str(val).strip()`, treat empty string and None as equivalent. This avoids false positives from `None` vs `""` differences in how pandas serializes absent fields.

## Dependencies

- `db.get_accounts_in_snapshot(snapshot_id, db_path)` — the only db.py function called
- `db.get_snapshots(db_path)` — used only by `compute_latest_delta` to find the two most recent IDs

## Out of Scope

- **Account rename detection** — if `name:foo-corp` becomes `cr:CR-123` because a CR ID was backfilled, the account will appear as dropped+new. Acceptable for now; fix if it causes coaching confusion.
- **Field-value semantic normalization** — "Yes" vs "yes" vs "TRUE" are treated as distinct. The spreadsheet export is from Salesforce, which should be consistent, so this hasn't caused issues yet.
- **Displaying the delta in the brief** — that's feature #13.
- **Storing the delta** — not needed yet; the delta is recomputable on demand from the snapshot pairs.

## Learnings

- **The field filter is the product decision, not an implementation detail.** Reporting every changed cell would drown the coach in noise. The explicit `COACHING_FIELDS` list encodes what the playbook cares about. When the playbook evolves, this list is the first place to look — it's the machine-readable equivalent of "what does the coach watch for."
- **Normalizing before comparing beats post-hoc filtering.** Coercing `None`, `""`, and whitespace-only to `""` before the comparison means the caller never sees spurious changes. Doing it after would require callers to filter noise, which they won't reliably do.
- **Building on `get_accounts_in_snapshot()` rather than direct SQL paid off immediately.** The delta logic stayed at ~80 lines with no sqlite3 imports. If the storage schema ever changes, `delta.py` doesn't care — it only depends on the dict shape that `db.py` already tests for.
- **`compute_latest_delta` is deceptively useful.** The two-liner convenience function (`get two IDs, diff them`) is what every caller actually wants. Without it, every caller would re-implement the "get the two most recent IDs" pattern — and probably get the ordering wrong once.
