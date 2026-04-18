"""Week-over-week delta detection for territory snapshots.

Compares two snapshots and surfaces what changed, what's new, and what dropped.
Builds on `get_accounts_in_snapshot()` from db.py — no direct DB queries here.

The focused field list is intentional: we only flag changes that affect coaching
decisions. Billing City changing tells us nothing; "Open Opp?" flipping to Yes
tells us everything.
"""

import json
from typing import Optional

from db import get_accounts_in_snapshot, get_snapshots

# Fields that matter for coaching decisions.
# Strategy Bucket fields (the wedge plays):
COACHING_FIELDS = [
    "Price Increase %",
    "Open Opp?",
    "Assurance",
    "Invoice",
    "Travel",
    "Payments",
    "Notes",
    # Contextually important for timing and relationship:
    "Customer Renewal Date",
    "ESA Consultant",
]


def compute_delta(
    latest_snapshot_id: int,
    previous_snapshot_id: int,
    db_path=None,
) -> dict:
    """Compare two snapshots and return a structured delta.

    Returns a dict with:
        latest_snapshot_id   — the newer snapshot
        previous_snapshot_id — the older snapshot
        new_accounts         — accounts in latest but not in previous
        dropped_accounts     — accounts in previous but not in latest
        changed_accounts     — accounts present in both with coaching-relevant field changes
            Each changed entry: {account_id, account_name, changes: {field: {before, after}}}

    Only COACHING_FIELDS are checked for changes. Changes in administrative
    fields (billing city, etc.) are intentionally ignored — they don't affect
    what plays the coach would recommend.

    Args:
        latest_snapshot_id:   snapshot ID for the newer upload.
        previous_snapshot_id: snapshot ID for the older upload.
        db_path:              optional path override, forwarded to db.py.

    Returns:
        Delta dict as described above.
    """
    latest_rows = get_accounts_in_snapshot(latest_snapshot_id, db_path)
    previous_rows = get_accounts_in_snapshot(previous_snapshot_id, db_path)

    latest_by_id = {r["account_id"]: r for r in latest_rows}
    previous_by_id = {r["account_id"]: r for r in previous_rows}

    latest_ids = set(latest_by_id.keys())
    previous_ids = set(previous_by_id.keys())

    new_accounts = [latest_by_id[aid] for aid in sorted(latest_ids - previous_ids)]
    dropped_accounts = [previous_by_id[aid] for aid in sorted(previous_ids - latest_ids)]

    changed_accounts = []
    for account_id in sorted(latest_ids & previous_ids):
        latest_row = latest_by_id[account_id]
        previous_row = previous_by_id[account_id]

        changes = _diff_coaching_fields(
            before=previous_row["row_data"],
            after=latest_row["row_data"],
        )
        if changes:
            changed_accounts.append(
                {
                    "account_id": account_id,
                    "account_name": latest_row["account_name"],
                    "changes": changes,
                }
            )

    return {
        "latest_snapshot_id": latest_snapshot_id,
        "previous_snapshot_id": previous_snapshot_id,
        "new_accounts": new_accounts,
        "dropped_accounts": dropped_accounts,
        "changed_accounts": changed_accounts,
    }


def compute_latest_delta(db_path=None) -> Optional[dict]:
    """Auto-find the two most recent snapshots and compute their delta.

    Returns None if fewer than 2 snapshots exist. Convenience wrapper for
    callers who just want "what changed since last time" without caring about
    specific snapshot IDs.

    Args:
        db_path: optional path override, forwarded to db.py.

    Returns:
        Delta dict (same shape as compute_delta) or None.
    """
    snapshots = get_snapshots(db_path)
    if len(snapshots) < 2:
        return None

    # get_snapshots returns newest-first; [0] is latest, [1] is previous.
    latest_id = snapshots[0]["id"]
    previous_id = snapshots[1]["id"]
    return compute_delta(latest_id, previous_id, db_path)


# ----- Formatting helpers -----

def format_delta_for_brief(delta: dict) -> str:
    """Render a delta dict as a markdown section for inclusion in the coaching brief.

    Produces scannable output: new accounts (with key fields), dropped accounts,
    and per-changed-account field/before/after. Returns an empty string if the
    delta has no changes so the caller can skip the section entirely.

    Args:
        delta: dict with the same shape as compute_delta() output.

    Returns:
        Markdown string (with leading newline stripped), or "" if no changes.
    """
    new_accounts = delta.get("new_accounts", [])
    dropped_accounts = delta.get("dropped_accounts", [])
    changed_accounts = delta.get("changed_accounts", [])

    if not new_accounts and not dropped_accounts and not changed_accounts:
        return ""

    lines: list[str] = ["## What Changed Since Last Upload"]

    # ── New accounts ──────────────────────────────────────────────────────────
    if new_accounts:
        lines.append(f"\n**NEW this week ({len(new_accounts)}):**")
        for entry in new_accounts:
            name = entry.get("account_name", entry.get("account_id", "Unknown"))
            row = entry.get("row_data", {})
            # Surface a handful of useful key fields if present
            key_parts: list[str] = []
            renewal = row.get("Customer Renewal Date")
            if renewal:
                key_parts.append(f"renewal {renewal}")
            pi = row.get("Price Increase %") or row.get("Price Increase $")
            if pi:
                key_parts.append(f"PI {pi}")
            opp = row.get("Open Opp?")
            if opp and str(opp).strip().lower() not in ("", "no"):
                key_parts.append("open opp")
            detail = f" — {', '.join(key_parts)}" if key_parts else ""
            lines.append(f"  - {name}{detail}")

    # ── Dropped accounts ──────────────────────────────────────────────────────
    if dropped_accounts:
        lines.append(f"\n**DROPPED this week ({len(dropped_accounts)}):**")
        for entry in dropped_accounts:
            name = entry.get("account_name", entry.get("account_id", "Unknown"))
            lines.append(f"  - {name} (removed from territory?)")

    # ── Changed accounts ──────────────────────────────────────────────────────
    if changed_accounts:
        lines.append(f"\n**CHANGED ({len(changed_accounts)} accounts):**")
        for entry in changed_accounts:
            name = entry.get("account_name", entry.get("account_id", "Unknown"))
            changes = entry.get("changes", {})
            lines.append(f"  - **{name}**")
            for field, vals in changes.items():
                before = _normalize_value(vals.get("before"))
                after = _normalize_value(vals.get("after"))
                lines.append(f"    - {field}: `{before or '(blank)'}` → `{after or '(blank)'}`")

    return "\n".join(lines)


# ----- Internal helpers -----

def _normalize_value(val) -> str:
    """Coerce a field value to a comparable string.

    Handles None, numeric, and string values consistently so that
    None vs "" and 0 vs "" don't generate spurious change signals.
    """
    if val is None:
        return ""
    return str(val).strip()


def _diff_coaching_fields(before: dict, after: dict) -> dict:
    """Return a {field: {before, after}} dict for COACHING_FIELDS that changed.

    Empty string and None are treated as equivalent (both mean "not set").
    """
    changes = {}
    for field in COACHING_FIELDS:
        before_val = _normalize_value(before.get(field))
        after_val = _normalize_value(after.get(field))
        if before_val != after_val:
            changes[field] = {
                "before": before.get(field),
                "after": after.get(field),
            }
    return changes
