"""Visual brief layout helpers.

Pure functions for the visual layer of the brief output:
  - format_arr: human-readable currency formatting for the metrics row
  - compute_brief_metrics: deterministic stats from the snapshot dataframe
  - parse_brief_sections: split brief markdown into structured sections by H2 markers

These are decoupled from Streamlit so they're unit-testable. The app.py layer
calls them and hands the results to st.metric / st.container / st.markdown.
"""

import re
from datetime import date
from typing import Optional

import pandas as pd

# H2 marker: line starting with exactly "## " (not "###" or deeper).
# `^##` matches the two hashes at line start; the `(?!#)` lookahead rejects
# anything that has a third hash; `\s+` requires the conventional space.
_H2_PATTERN = re.compile(r"^##(?!#)\s+(.+)$")

# Column names per Matt's SOP.
_RENEWAL_COL = "Customer Renewal Date"
_ARR_COL = "Active Subscriptions ARR Rollup"
_OPEN_OPP_COL = "Open Opp?"

# Open Opp values that mean "the renewal is being worked" (so NOT a fire).
_OPEN_OPP_HAS_OPP = {"Y", "WORKING"}


# ────────────────────────────────────────────────────────────────────────


def format_arr(value: Optional[float]) -> str:
    """Format an ARR amount for the metrics row.

    Examples:
        None      → "—"
        0         → "$0"
        750       → "$750"
        412000    → "$412K"
        1850000   → "$1.85M"
        2000000   → "$2M"     (trailing zeros trimmed)
    """
    if value is None:
        return "—"
    value = float(value)
    if value == 0:
        return "$0"
    if value < 1000:
        return f"${int(value)}"
    if value < 1_000_000:
        return f"${int(value / 1000)}K"
    millions = value / 1_000_000
    formatted = f"{millions:.2f}".rstrip("0").rstrip(".")
    return f"${formatted}M"


# ────────────────────────────────────────────────────────────────────────


def compute_brief_metrics(
    df: pd.DataFrame, today: Optional[date] = None
) -> dict:
    """Compute the at-a-glance metrics shown above the brief.

    Returns a dict with keys:
      - total_accounts: int (always present)
      - arr_at_risk: Optional[int] — sum of ARR for accounts renewing in next 120 days
      - red_zone_fires: Optional[int] — count of those accounts with no Open Opp
      - days_to_next_renewal: Optional[int] — smallest positive day count to a renewal

    Any metric whose source column is missing returns None — the UI shows "—"
    in that slot rather than crashing.
    """
    if today is None:
        today = date.today()

    metrics: dict = {
        "total_accounts": len(df),
        "arr_at_risk": None,
        "red_zone_fires": None,
        "days_to_next_renewal": None,
    }

    cols = set(df.columns)
    if _RENEWAL_COL not in cols:
        return metrics

    renewals = pd.to_datetime(df[_RENEWAL_COL], errors="coerce")
    days_to = (renewals - pd.Timestamp(today)).dt.days

    red_zone_mask = (days_to >= 0) & (days_to <= 120)

    if _ARR_COL in cols:
        arr_values = pd.to_numeric(df[_ARR_COL], errors="coerce").fillna(0)
        metrics["arr_at_risk"] = int(arr_values[red_zone_mask].sum())

    if _OPEN_OPP_COL in cols:
        opp_values = df[_OPEN_OPP_COL].astype(str).str.strip().str.upper()
        no_opp_mask = ~opp_values.isin(_OPEN_OPP_HAS_OPP)
        metrics["red_zone_fires"] = int((red_zone_mask & no_opp_mask).sum())

    future_days = days_to[days_to > 0]
    if len(future_days) > 0:
        metrics["days_to_next_renewal"] = int(future_days.min())

    return metrics


# ────────────────────────────────────────────────────────────────────────


def parse_brief_sections(brief_markdown: str) -> list[dict]:
    """Split a brief into sections by H2 markdown markers.

    Returns a list of section dicts: {heading, body, kind}.

    `kind` is one of:
      'headline'     — pre-first-H2 prose (labeled "Today's Headline")
      'fires'        — Red Zone section (matched on 🔴 or "fire" keyword)
      'leverage'     — Strategy Zone (🟠 / "leverage" / "strategy")
      'slow_burns'   — mid-term reviews (🟢 / "slow burn" / "mid-term")
      'questions'    — "What I/You Don't Know" sections
      'other'        — recognized H2 that doesn't match a canonical zone
      'unstructured' — fallback when the brief has no H2 markers at all

    Source order is preserved. Empty / whitespace-only briefs return [].
    """
    if not brief_markdown or not brief_markdown.strip():
        return []

    sections: list[dict] = []
    current_heading: Optional[str] = None
    current_body_lines: list[str] = []
    saw_h2 = False

    def _flush() -> None:
        body = "\n".join(current_body_lines).strip()
        if current_heading is None:
            # Pre-first-H2 content becomes the headline (skip if empty).
            if body:
                sections.append({
                    "heading": "Today's Headline",
                    "body": body,
                    "kind": "headline",
                })
        else:
            sections.append({
                "heading": current_heading,
                "body": body,
                "kind": _classify_section(current_heading),
            })

    for line in brief_markdown.split("\n"):
        match = _H2_PATTERN.match(line)
        if match:
            _flush()
            current_heading = match.group(1).strip()
            current_body_lines = []
            saw_h2 = True
        else:
            current_body_lines.append(line)

    _flush()

    # If we never saw an H2, the single section is unstructured (not a "headline").
    if not saw_h2 and sections:
        sections[0]["kind"] = "unstructured"
        sections[0]["heading"] = None

    return sections


def _classify_section(heading: str) -> str:
    """Map a section heading to a canonical kind."""
    h = heading.lower()
    if "🔴" in heading or "fire" in h:
        return "fires"
    if "🟠" in heading or "leverage" in h or "strategy" in h:
        return "leverage"
    if "🟢" in heading or "slow burn" in h or "mid-term" in h or "midterm" in h:
        return "slow_burns"
    if "don't know" in h or "dont know" in h:
        return "questions"
    return "other"
