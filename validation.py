"""Pre-flight column validation for territory uploads.

Validates the shape of a territory DataFrame's columns BEFORE the LLM call.
Complements the LLM-side Ground Truth check in system_prompt.md — both layers
should exist. This layer is deterministic and cheap; the LLM layer adds prose
and coaching context to whatever warnings surface here.

Usage:
    from validation import validate_columns
    result = validate_columns(df.columns.tolist())
    # result["warnings"] is a list of human-readable strings suitable for
    # surfacing in the UI or prepending to the brief.
"""

# Standard Salesforce export fields — should always be present.
STANDARD_FIELDS: list[str] = [
    "Brand",
    "Account Owner",
    "Account Name",
    "Customer Renewal Date",
    "Customer Success Manager",
    "CR Customer ID",
    "Active Subscriptions ARR Rollup",
    "ESA Consultant",
    "Billing City",
    "Billing State",
    "Employees",
    "Type",
]

# Strategy Bucket fields — manual overlay, frequently missing.
# "Price Increase" is listed as two variants in Matt's docs; either satisfies
# the bucket. All others must match exactly.
_STRATEGY_BUCKET_EXACT: list[str] = [
    "Open Opp?",
    "Assurance",
    "Invoice",
    "Travel",
    "Payments",
    "Notes",
]

# The two acceptable column names for the price-increase bucket.
_PRICE_INCREASE_VARIANTS: tuple[str, ...] = (
    "Price Increase %",
    "Price Increase $",
)

# Canonical name used in missing / warning output when neither variant found.
_PRICE_INCREASE_CANONICAL = "Price Increase % (or Price Increase $)"

# Full expected set for "extra" calculation (includes both PI variants so
# either one is treated as known).
_ALL_KNOWN: frozenset[str] = frozenset(
    STANDARD_FIELDS + _STRATEGY_BUCKET_EXACT + list(_PRICE_INCREASE_VARIANTS)
)


def validate_columns(df_columns: list[str]) -> dict:
    """Validate column shape of a territory upload.

    Args:
        df_columns: list of column name strings from the uploaded DataFrame.

    Returns a dict with four keys:
        missing_standard (list[str]):
            Standard Salesforce fields absent from the upload.
        missing_strategy_buckets (list[str]):
            Strategy Bucket fields absent from the upload. Uses the canonical
            name for the Price Increase bucket if neither variant is present.
        extra (list[str]):
            Columns present that belong to neither the standard nor strategy-
            bucket sets.
        warnings (list[str]):
            Human-readable strings in the Matthew Rollins voice describing
            what coaching capability is degraded. Empty list when shape is
            clean.
    """
    col_set = set(df_columns)

    # ── Standard fields ────────────────────────────────────────────────────
    missing_standard = [f for f in STANDARD_FIELDS if f not in col_set]

    # ── Strategy bucket fields ─────────────────────────────────────────────
    missing_strategy: list[str] = []

    # Price Increase: accept either variant
    pi_present = any(v in col_set for v in _PRICE_INCREASE_VARIANTS)
    if not pi_present:
        missing_strategy.append(_PRICE_INCREASE_CANONICAL)

    for field in _STRATEGY_BUCKET_EXACT:
        if field not in col_set:
            missing_strategy.append(field)

    # ── Extra columns ──────────────────────────────────────────────────────
    extra = sorted(c for c in col_set if c not in _ALL_KNOWN)

    # ── Warnings ───────────────────────────────────────────────────────────
    warnings: list[str] = []

    if missing_standard:
        field_list = ", ".join(missing_standard)
        warnings.append(
            f"Missing standard Salesforce fields: {field_list}. "
            "The brief will be less reliable — core account data is incomplete."
        )

    if missing_strategy:
        field_list = ", ".join(missing_strategy)
        warnings.append(
            f"Missing Strategy Bucket columns: {field_list}. "
            "Whitespace plays in the Strategy Zone will be thinner until you add them."
        )

    return {
        "missing_standard": missing_standard,
        "missing_strategy_buckets": missing_strategy,
        "extra": extra,
        "warnings": warnings,
    }
