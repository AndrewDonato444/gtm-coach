---
feature: Upload history view in Streamlit
domain: storage
source: pages/01_Upload_History.py
tests: []
components:
  - pages/01_Upload_History.py
  - db.py
design_refs: []
status: implemented
created: 2026-04-17
updated: 2026-04-17
---

# Upload History View in Streamlit

**Purpose:** Give the rep (and leader) a quick way to see every territory upload that has been persisted, and to drill into any snapshot's full DataFrame. Built as a Streamlit multipage companion to `app.py` — auto-discovered from the `pages/` directory so `app.py` is not modified.

**Source File:** `pages/01_Upload_History.py`
**DB Functions Consumed:** `db.get_snapshots()`, `db.get_snapshot(id)`

---

## Feature: Upload History Page

### Scenario: Empty state — no uploads yet
Given the SQLite database has no snapshots
When the rep navigates to the Upload History page
Then they see a friendly info message: "No territory uploads yet — go to the main page and upload one"
And no table or selectbox is shown

### Scenario: List of uploads renders newest first
Given the database contains three snapshots saved at different times
When the rep navigates to the Upload History page
Then a summary table is shown with columns: ID, Uploaded At, Source Filename, Row Count
And the rows are ordered newest first (matching `get_snapshots()` ordering)
And the total upload count is shown in the subheader

### Scenario: Rep selects a snapshot to inspect
Given the summary table shows multiple snapshots
When the rep selects snapshot #2 from the selectbox
Then `get_snapshot(2)` is called
And the full DataFrame for snapshot #2 is shown via `st.dataframe`
And the three metrics (Snapshot ID, Row Count, Uploaded At) are displayed
And the column list and source filename are shown as captions

### Scenario: Unknown snapshot ID (defensive case)
Given the rep somehow selects an ID that no longer exists in the DB
When `get_snapshot(id)` returns None
Then an error message is shown: "Snapshot #{id} could not be found. The database may have changed."

### Scenario: Source filename is null
Given a snapshot was saved with a None source_filename (e.g. uploaded without a name)
When the summary table and inspector render
Then the filename column shows "(unknown)" instead of None or blank

---

## UI Mockup

```
┌─────────────────────────────────────────────────────────────────┐
│ GTM Coach                                                       │
│ ● GTM Coach — Prototype  (sidebar nav)                         │
│ ● Upload History         (this page)                           │
├─────────────────────────────────────────────────────────────────┤
│ Upload History                                                  │
│ Every territory upload, newest first. Select one to inspect.   │
│                                                                 │
│ 3 uploads on record                                             │
│ ┌────┬─────────────────────┬─────────────────────┬───────────┐ │
│ │ ID │ Uploaded At         │ Source Filename      │ Row Count │ │
│ ├────┼─────────────────────┼─────────────────────┼───────────┤ │
│ │  3 │ 2026-04-17T09:42:11 │ territory_apr17.xlsx │        87 │ │
│ │  2 │ 2026-04-10T14:22:05 │ territory_apr10.xlsx │        85 │ │
│ │  1 │ 2026-04-03T08:15:33 │ test_territory.xlsx  │        82 │ │
│ └────┴─────────────────────┴─────────────────────┴───────────┘ │
│                                                                 │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ Inspect a snapshot                                              │
│                                                                 │
│ Choose a snapshot to view its full territory data:             │
│ [#3 — 2026-04-17T09:42:11 (territory_apr17.xlsx, 87 rows) ▼]  │
│                                                                 │
│ ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│ │ Snapshot ID  │ │  Row Count   │ │     Uploaded At        │   │
│ │      3       │ │     87       │ │ 2026-04-17T09:42:11    │   │
│ └──────────────┘ └──────────────┘ └───────────────────────┘   │
│                                                                 │
│ Source file: territory_apr17.xlsx                              │
│ Columns: Account Name, ARR, Renewal Date, CR Customer ID, ...  │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Account Name  │ ARR    │ Renewal Date │ CR Customer ID │ … │ │
│ ├───────────────┼────────┼──────────────┼────────────────┼───┤ │
│ │ Acme Corp     │ 100000 │ 2026-09-15   │ CR-1001        │ … │ │
│ │ Globex Inc    │ 250000 │ 2027-01-20   │ CR-1002        │ … │ │
│ │ ...           │ ...    │ ...          │ ...            │   │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Empty State

```
┌─────────────────────────────────────────────────────────────────┐
│ Upload History                                                  │
│ Every territory upload, newest first. Select one to inspect.   │
│                                                                 │
│ 📂 No territory uploads yet — go to the main page and upload   │
│    one.                                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Testing Notes

**Why there is no `tests/test_history.py`:**

Streamlit pages don't expose any pure-Python logic beyond UI orchestration calls. The page's entire body is:

1. Call `get_snapshots()` — covered by `tests/test_db.py`
2. Call `get_snapshot(id)` — covered by `tests/test_db.py`
3. Pass the results to Streamlit widgets (`st.dataframe`, `st.selectbox`, etc.)

Step 3 is only testable via Streamlit's `AppTest` / `ScriptRunner` harness (available in Streamlit ≥ 1.28). That harness requires running the full Streamlit script in a subprocess and is not appropriate for a unit test suite. The data-shaping step (building `summary_rows` from snapshot dicts) is trivial enough (a list comprehension with a None-guard) that a dedicated unit test would add noise without catching real bugs.

**Decision:** skip `tests/test_history.py`. The DB layer is tested. The UI layer is integration-tested manually via `streamlit run app.py`.

---

## Learnings

- **Streamlit multipage requires zero changes to `app.py`.** Drop a file in `pages/` with a digit prefix (`01_…`) and Streamlit auto-discovers it, adds it to the sidebar, and handles routing. The "throwaway shell" principle from Phase 1 held perfectly — extending the UI is additive, not invasive.

- **`pages/` scripts run with cwd = project root.** Streamlit sets the working directory to the root of the app (where `app.py` lives), so `from db import …` resolves without any `sys.path` manipulation. Similarly, `Path(__file__).parent.parent` correctly walks from `pages/` up to the project root for dotenv loading.

- **`py_compile` is the right syntax check for digit-prefixed filenames.** Python's module import system rejects identifiers starting with a digit (`01_Upload_History`), so `python -c "import pages.01_Upload_History"` fails at the parser level. Bytecode compilation (`python -m py_compile pages/01_Upload_History.py`) is the correct verification path and is independent of import mechanics.

- **`st.stop()` after empty-state is the idiomatic Streamlit guard.** Rather than nesting the entire page in an `if snapshots:` block, calling `st.stop()` after the info message keeps the code flat. Streamlit stops rendering and no widgets below the call execute — clean and readable.
