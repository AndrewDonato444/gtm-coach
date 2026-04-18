---
feature: "What changed since last upload" section in brief
domain: coaching
source: app.py
tests:
  - tests/test_delta.py
components:
  - delta.py
  - app.py
  - system_prompt.md
design_refs: []
status: implemented
created: 2026-04-17
updated: 2026-04-17
---

# "What Changed Since Last Upload" in Brief

**Source Files**: `app.py`, `delta.py`, `system_prompt.md`
**Depends on**: feature #12 (delta detection), feature #10 (snapshots)

## Purpose

Surface what actually changed between the rep's last upload and this one, injected into the coaching brief before the territory data. This is the single biggest leverage point in the Phase 2 build — it turns the coach from a static territory analyzer into a system that *watches* the territory move week over week. A coach who sees the diff is better than a coach who only sees the snapshot.

## Feature: Delta Section in user_message

### Scenario: Single snapshot — no delta section
Given the database has exactly 1 snapshot (this is the first upload)
When the rep clicks "Coach me"
Then `compute_latest_delta()` returns None
And the "What Changed Since Last Upload" section is omitted from the user_message
And the brief is generated from the static territory data only

### Scenario: Two or more snapshots, no coaching-field changes
Given the database has 2 or more snapshots
And the delta between the two most recent has no new, dropped, or changed accounts
When the rep clicks "Coach me"
Then `format_delta_for_brief()` returns an empty string
And the "What Changed Since Last Upload" section is omitted from the user_message

### Scenario: New accounts detected — injected between Summary and Territory Data
Given the database has 2 snapshots
And the latest snapshot has 1 new account (Initech Corp, renewal 2026-09-01)
When the rep clicks "Coach me"
Then the user_message contains "## What Changed Since Last Upload"
And the section appears after "## Summary" and before "## Territory Data"
And the section lists "Initech Corp" with its renewal date

### Scenario: Changed accounts show field-level diff
Given the database has 2 snapshots
And Acme's "Open Opp?" changed from "No" to "Yes"
When the rep clicks "Coach me"
Then the user_message contains "CHANGED" with Acme listed
And the entry shows `Open Opp?` with before and after values

### Scenario: Dropped accounts listed with flag
Given the database has 2 snapshots
And Globex was in the previous snapshot but not the latest
When the rep clicks "Coach me"
Then the "DROPPED" subsection names Globex
And indicates it may have been removed from territory

## Feature: LLM Behavior When Delta Present

### Scenario: Delta headline leads the brief
Given the user_message contains a "What Changed Since Last Upload" section
And Acme flipped "Open Opp?" from No to Yes this week
When the LLM generates the brief
Then the brief leads with the Acme opp change as the headline
And does not open with a generic static territory summary

### Scenario: New account gets orientation call-out
Given the user_message includes a new account in the delta section
When the LLM generates the brief
Then the brief includes a quick orientation for that new account
Noting why it matters and what play the data suggests

## Updated user_message Structure

When all sections are present, the user_message flows in this order:

```
Here is the rep's territory export.

## Summary
Rows: N | Columns: ...

## What Changed Since Last Upload          ← injected if delta has changes
**NEW this week (N):**
  - Account Name — renewal date, PI %

**DROPPED this week (N):**
  - Account Name (removed from territory?)

**CHANGED (N accounts):**
  - **Account Name**
    - Field: `before` → `after`

## Territory Data
| ... full markdown table ... |

## Data Quality                             ← injected if validation warnings exist
- Warning string 1
- Warning string 2

## Rep's Context
(free-text from the rep, or "(none provided)")
```

If delta has no changes: the "What Changed" section is omitted entirely.
If validation has no warnings: the "Data Quality" section is omitted entirely.

## ASCII Mockup

```
┌─────────────────────────────────────────────────────────┐
│ GTM Coach — Brief                                       │
│                                                         │
│  ⚠ Missing Strategy Bucket columns: Assurance.         │
│    Whitespace plays in the Strategy Zone will be        │
│    thinner until you add them.                          │
│                                                         │
│  [ Coach me ]                                           │
│                                                         │
│  ─── Brief streams here ───                             │
│                                                         │
│  HEADLINE: Acme opened an opp this week.                │
│  That's the play.                                       │
│                                                         │
│  🔴 The fires ...                                       │
│  🟠 The leverage plays ...                              │
│  🟢 The slow burns ...                                  │
└─────────────────────────────────────────────────────────┘
```

## Learnings

- **Ordering the user_message sections matters more than it looks.** Placing the delta before Territory Data means the LLM reads "what changed" before it reads the full static territory, which steers the reasoning toward the diff rather than the steady state. Section order is a prompt engineering decision embedded in the orchestrator.
- **`format_delta_for_brief` belongs in delta.py, not app.py.** The formatter knows the delta schema intimately and has the `_normalize_value` helper already. Keeping it colocated with `compute_delta` means a single file owns both the shape and the rendering — and the tests live in the same test file.
- **The empty-string contract is load-bearing.** `format_delta_for_brief` returning `""` when there are no changes lets the orchestrator use a simple truthiness check. Any other sentinel (None, empty dict) would push conditional logic into the caller. A pure function that returns a renderable string or nothing is the cleanest API for this use case.
- **The LLM behavior change (system_prompt.md addition) is higher-leverage than the data injection.** Without the "When delta context is present" section, the LLM might bury the delta or ignore it in favor of its static analysis order. The prompt tells it explicitly: the diff is the lead. This validates the roadmap principle that prompt edits are first-class work.
