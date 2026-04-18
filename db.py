"""Territory snapshot storage layer.

Persists every uploaded territory as a snapshot so future Phase 2+ features
(delta detection, feedback loop, scheduled briefs) can build on a historical
record. Implements vision principle #5: the spreadsheet is the seed, not the
substrate.
"""

import json
import re
import sqlite3
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_DB_PATH = Path(__file__).parent / "storage.db"


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Create the snapshots and account_rows tables if they don't already exist."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                uploaded_at     TEXT NOT NULL,
                source_filename TEXT,
                row_count       INTEGER NOT NULL,
                column_names    TEXT NOT NULL,
                raw_data        TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_rows (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id   INTEGER NOT NULL REFERENCES snapshots(id),
                account_id    TEXT NOT NULL,
                account_name  TEXT,
                row_data      TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_rows_account ON account_rows(account_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_rows_snapshot ON account_rows(snapshot_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS briefs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id       INTEGER NOT NULL REFERENCES snapshots(id),
                generated_at      TEXT NOT NULL,
                brief_text        TEXT NOT NULL,
                rep_context       TEXT,
                model             TEXT,
                input_tokens      INTEGER,
                output_tokens     INTEGER,
                cache_read_tokens INTEGER
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_briefs_snapshot ON briefs(snapshot_id)"
        )


def _normalize_account_id(row: dict) -> str:
    """Derive a stable account ID from a row dict.

    Priority:
        1. cr:{CR Customer ID}   — authoritative when present
        2. name:{slugified name} — fallback when CR ID is missing/blank
        3. ValueError            — when neither is usable

    The prefix tells future code which strategy was used so renames or
    backfills can be reasoned about explicitly.
    """
    cr_id = row.get("CR Customer ID")
    if cr_id is not None and str(cr_id).strip():
        return f"cr:{str(cr_id).strip()}"

    name = row.get("Account Name")
    if name is not None and str(name).strip():
        slug = re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-")
        if slug:
            return f"name:{slug}"

    raise ValueError(
        "Cannot normalize account: row has neither CR Customer ID nor Account Name"
    )


def save_snapshot(
    df: pd.DataFrame,
    source_filename: str,
    db_path: Optional[Path] = None,
) -> tuple[int, str, bool]:
    """Persist a territory upload. Returns (snapshot_id, uploaded_at_iso, is_new).

    If the new upload's content (columns + row data) is identical to the latest
    existing snapshot, no new row is inserted — the existing snapshot's ID and
    timestamp are returned with is_new=False. This prevents double-clicks and
    accidental re-uploads from polluting the snapshot history (and breaking
    delta detection, which always compares the two newest snapshots).

    Side effect: also populates `account_rows` with one row per account,
    keyed by normalized account_id. Rows that can't be normalized (no CR ID
    and no Account Name) are skipped — they're unreachable for future delta
    detection anyway.
    """
    init_db(db_path)
    uploaded_at = datetime.now().isoformat(timespec="seconds")
    column_names_json = json.dumps(df.columns.tolist())
    raw_data_json = df.to_json(orient="records")

    # Dedup: if latest snapshot has identical columns + data, reuse its ID.
    with _connect(db_path) as conn:
        latest = conn.execute(
            "SELECT id, uploaded_at, column_names, raw_data FROM snapshots "
            "ORDER BY uploaded_at DESC, id DESC LIMIT 1"
        ).fetchone()
        if (
            latest is not None
            and latest["column_names"] == column_names_json
            and latest["raw_data"] == raw_data_json
        ):
            return latest["id"], latest["uploaded_at"], False

    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO snapshots
                (uploaded_at, source_filename, row_count, column_names, raw_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (uploaded_at, source_filename, len(df), column_names_json, raw_data_json),
        )
        snapshot_id = cur.lastrowid

        for row_dict in df.to_dict(orient="records"):
            try:
                account_id = _normalize_account_id(row_dict)
            except ValueError:
                continue  # un-trackable row; raw_data still preserves it
            account_name = row_dict.get("Account Name")
            conn.execute(
                """
                INSERT INTO account_rows (snapshot_id, account_id, account_name, row_data)
                VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    account_id,
                    str(account_name) if account_name is not None else None,
                    json.dumps(row_dict),
                ),
            )

    return snapshot_id, uploaded_at, True


def _row_to_snapshot(row: sqlite3.Row, include_dataframe: bool) -> dict:
    snapshot = {
        "id": row["id"],
        "uploaded_at": row["uploaded_at"],
        "source_filename": row["source_filename"],
        "row_count": row["row_count"],
        "column_names": json.loads(row["column_names"]),
    }
    if include_dataframe:
        snapshot["dataframe"] = pd.read_json(
            StringIO(row["raw_data"]), orient="records"
        )
    return snapshot


def get_latest_snapshot(db_path: Optional[Path] = None) -> Optional[dict]:
    """Return the most recently uploaded snapshot (with dataframe), or None."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM snapshots ORDER BY uploaded_at DESC, id DESC LIMIT 1"
        ).fetchone()
    return _row_to_snapshot(row, include_dataframe=True) if row else None


def get_snapshots(db_path: Optional[Path] = None) -> list[dict]:
    """Return summaries of all snapshots, newest first. No dataframe payload."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM snapshots ORDER BY uploaded_at DESC, id DESC"
        ).fetchall()
    return [_row_to_snapshot(row, include_dataframe=False) for row in rows]


def get_snapshot(
    snapshot_id: int, db_path: Optional[Path] = None
) -> Optional[dict]:
    """Return a single snapshot (with dataframe) by ID, or None."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
    return _row_to_snapshot(row, include_dataframe=True) if row else None


def get_account_history(
    account_id: str, db_path: Optional[Path] = None
) -> list[dict]:
    """Return all snapshot rows for one account, oldest first.

    Each entry: {snapshot_id, uploaded_at, row_data (parsed dict)}.
    """
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT ar.snapshot_id, ar.row_data, s.uploaded_at
            FROM account_rows ar
            JOIN snapshots s ON s.id = ar.snapshot_id
            WHERE ar.account_id = ?
            ORDER BY s.uploaded_at ASC, ar.snapshot_id ASC
            """,
            (account_id,),
        ).fetchall()
    return [
        {
            "snapshot_id": row["snapshot_id"],
            "uploaded_at": row["uploaded_at"],
            "row_data": json.loads(row["row_data"]),
        }
        for row in rows
    ]


def save_brief(
    snapshot_id: int,
    brief_text: str,
    rep_context: Optional[str] = None,
    model: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    cache_read_tokens: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> tuple[int, str]:
    """Persist a generated brief linked to its source snapshot.

    Returns (brief_id, generated_at_iso).
    """
    init_db(db_path)
    generated_at = datetime.now().isoformat(timespec="seconds")
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO briefs
                (snapshot_id, generated_at, brief_text, rep_context, model,
                 input_tokens, output_tokens, cache_read_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                generated_at,
                brief_text,
                rep_context,
                model,
                input_tokens,
                output_tokens,
                cache_read_tokens,
            ),
        )
        brief_id = cur.lastrowid
    return brief_id, generated_at


def _row_to_brief(row: sqlite3.Row, include_text: bool) -> dict:
    brief = {
        "id": row["id"],
        "snapshot_id": row["snapshot_id"],
        "generated_at": row["generated_at"],
        "rep_context": row["rep_context"],
        "model": row["model"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "cache_read_tokens": row["cache_read_tokens"],
    }
    if include_text:
        brief["brief_text"] = row["brief_text"]
    return brief


def get_briefs(db_path: Optional[Path] = None) -> list[dict]:
    """Return summaries of all briefs, newest first. No brief_text payload."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM briefs ORDER BY generated_at DESC, id DESC"
        ).fetchall()
    return [_row_to_brief(row, include_text=False) for row in rows]


def get_brief(
    brief_id: int, db_path: Optional[Path] = None
) -> Optional[dict]:
    """Return a single brief (with full text) by ID, or None."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM briefs WHERE id = ?", (brief_id,)
        ).fetchone()
    return _row_to_brief(row, include_text=True) if row else None


def get_accounts_in_snapshot(
    snapshot_id: int, db_path: Optional[Path] = None
) -> list[dict]:
    """Return all account rows for one snapshot.

    Each entry: {account_id, account_name, row_data (parsed dict)}.
    """
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT account_id, account_name, row_data
            FROM account_rows
            WHERE snapshot_id = ?
            ORDER BY id ASC
            """,
            (snapshot_id,),
        ).fetchall()
    return [
        {
            "account_id": row["account_id"],
            "account_name": row["account_name"],
            "row_data": json.loads(row["row_data"]),
        }
        for row in rows
    ]
