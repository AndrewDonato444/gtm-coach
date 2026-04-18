---
feature: Header / Strategy Bucket validation in pre-flight
domain: storage
source: validation.py
tests:
  - tests/test_validation.py
components:
  - validation.py
design_refs: []
status: implemented
created: 2026-04-17
updated: 2026-04-17
---

# Header / Strategy Bucket Validation in Pre-Flight

**Source File**: `validation.py`
**Related**: `system_prompt.md` (LLM-side Ground Truth check), `app.py` (orchestrator wires the call)

## Purpose

Validate the shape of an uploaded territory DataFrame's columns **before** the LLM call is made. This is the deterministic, zero-cost layer that catches structural problems early. It complements — but does not replace — the LLM-side Ground Truth check in `system_prompt.md`. Both layers are intentional:

- **`validation.py` (this feature):** deterministic, runs before the API call, emits structured warnings the UI can display.
- **`system_prompt.md` Ground Truth check:** prose-level, runs inside the LLM, degrades gracefully and explains coaching impact in the coach's own voice.

The feature traces to Matt's source documents (System Instructions + SOP) which define the two column categories explicitly.

## Column Categories

**Standard fields** (Salesforce export — should always be present):
> Brand, Account Owner, Account Name, Customer Renewal Date, Customer Success Manager, CR Customer ID, Active Subscriptions ARR Rollup, ESA Consultant, Billing City, Billing State, Employees, Type

**Strategy Bucket fields** (manual overlay — often missing):
> Price Increase % (or Price Increase $), Open Opp?, Assurance, Invoice, Travel, Payments, Notes

Note: Matt's docs show both `Price Increase %` and `Price Increase $` in the wild. Either form satisfies the bucket.

## Feature: Pre-flight Column Validation

### Scenario: Full column set — no warnings
Given a DataFrame with all 12 standard fields and all 7 strategy bucket fields present
When `validate_columns(df.columns.tolist())` is called
Then `missing_standard` is empty
And `missing_strategy_buckets` is empty
And `warnings` is empty

### Scenario: All strategy buckets missing
Given a DataFrame with only the 12 standard fields (no strategy bucket columns)
When `validate_columns()` is called
Then `missing_strategy_buckets` contains all 7 bucket names (using canonical Price Increase name)
And `missing_standard` is empty
And `warnings` contains exactly one string
And that warning mentions "Strategy Zone"

### Scenario: Partial standard fields missing
Given a DataFrame that is missing Brand, Billing State, and Employees
When `validate_columns()` is called
Then `missing_standard` contains exactly ["Brand", "Billing State", "Employees"]
And `missing_strategy_buckets` is empty
And `warnings` contains one string naming the missing standard fields

### Scenario: Extra (unrecognized) columns reported
Given a DataFrame with all expected columns plus three unknown columns
When `validate_columns()` is called
Then the three unknown columns appear in `extra`
And `missing_standard` and `missing_strategy_buckets` are empty
And `warnings` is empty (extra columns don't degrade coaching)

### Scenario: "Price Increase $" accepted as alternative to "%"
Given a DataFrame with "Price Increase $" present (not "Price Increase %")
When `validate_columns()` is called
Then `missing_strategy_buckets` does not contain the Price Increase canonical name
And no warning about Price Increase is emitted

### Scenario: Both standard and strategy fields missing
Given a DataFrame that is missing some standard fields AND all strategy bucket fields
When `validate_columns()` is called
Then `warnings` contains exactly two strings
And one warning references "standard Salesforce fields"
And one warning references "Strategy Zone"

### Scenario: Empty column list
Given `validate_columns([])` is called
Then `missing_standard` contains all 12 standard fields
And `missing_strategy_buckets` contains all 7 bucket names
And `warnings` contains exactly two strings

## Return Shape

```python
{
  "missing_standard": list[str],        # standard fields absent
  "missing_strategy_buckets": list[str], # strategy bucket fields absent
  "extra": list[str],                    # columns not in either expected set
  "warnings": list[str],                 # human-readable, Matthew Rollins voice
}
```

## Warning Tone

Warnings match the voice in `system_prompt.md` — direct, names what's disabled:

- Standard fields missing: `"Missing standard Salesforce fields: {names}. The brief will be less reliable — core account data is incomplete."`
- Strategy buckets missing: `"Missing Strategy Bucket columns: {names}. Whitespace plays in the Strategy Zone will be thinner until you add them."`

## UI Mockup

```
┌─────────────────────────────────────────────────────────┐
│ GTM Coach — Prototype                                   │
├─────────────────────────────────────────────────────────┤
│  ✓ territory_q2.xlsx                                    │
│                                                         │
│  ⚠ Missing Strategy Bucket columns: Assurance, Travel. │
│    Whitespace plays in the Strategy Zone will be        │
│    thinner until you add them.                          │
│                                                         │
│  [ Coach me ]                                           │
└─────────────────────────────────────────────────────────┘
```

Warnings surface between the file picker and the "Coach me" button so the rep can act before spending API tokens.

## Learnings

- **Two validator layers are better than one.** The deterministic pre-flight check (this file) and the LLM-side Ground Truth check in `system_prompt.md` serve different purposes and complement each other. The pre-flight layer is cheap, structured, and testable; the LLM layer adds prose coaching context. Neither replaces the other.
- **Accept both Price Increase variants at the data layer.** Matt's docs show `Price Increase %` and `Price Increase $` in the wild. The validator normalizes this silently — no warning, no fragile exact-match. Callers never need to know which variant was used.
- **Extra columns do not warrant a warning.** Reps frequently add their own columns to territory exports. Flagging them as errors would create noise that trains reps to ignore warnings. They belong in `extra` for informational use, nothing more.
- **stdlib only.** The validator imports nothing beyond Python builtins — no pandas, no numpy. This keeps it fast, dependency-free, and safe to call before any DataFrame is loaded if needed.
