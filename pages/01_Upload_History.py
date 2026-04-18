"""Upload History — GTM Coach companion page.

Lists all territory snapshot uploads, newest first. Lets the user inspect
the full DataFrame for any snapshot. Relies entirely on db.get_snapshots()
and db.get_snapshot() — no direct DB access in this file.

Run via the parent Streamlit app (auto-discovered from pages/ directory):
    streamlit run app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Match app.py's dotenv load pattern — look two levels up from this file
# (pages/ -> project root) for .env.local.
load_dotenv(Path(__file__).parent.parent / ".env.local")

# db.py lives at the project root. Streamlit's working directory is the
# project root when launched via `streamlit run app.py`, so the import works.
from db import get_snapshot, get_snapshots  # noqa: E402

st.set_page_config(page_title="Upload History — GTM Coach", layout="wide")
st.title("Upload History")
st.caption("Every territory upload, newest first. Select one to inspect its full data.")

snapshots = get_snapshots()

if not snapshots:
    st.info(
        "No territory uploads yet — go to the main page and upload one.",
        icon="📂",
    )
    st.stop()

# --- Summary table -----------------------------------------------------------

summary_rows = [
    {
        "ID": s["id"],
        "Uploaded At": s["uploaded_at"],
        "Source Filename": s["source_filename"] or "(unknown)",
        "Row Count": s["row_count"],
    }
    for s in snapshots
]

summary_df = pd.DataFrame(summary_rows)

st.subheader(f"{len(snapshots)} upload{'s' if len(snapshots) != 1 else ''} on record")
st.dataframe(summary_df, use_container_width=True, hide_index=True)

# --- Snapshot inspector ------------------------------------------------------

st.divider()
st.subheader("Inspect a snapshot")

snapshot_options = {
    f"#{s['id']} — {s['uploaded_at']} ({s['source_filename'] or 'unknown file'}, {s['row_count']} rows)": s["id"]
    for s in snapshots
}

selected_label = st.selectbox(
    "Choose a snapshot to view its full territory data:",
    options=list(snapshot_options.keys()),
)

if selected_label:
    selected_id = snapshot_options[selected_label]
    with st.spinner(f"Loading snapshot #{selected_id}..."):
        detail = get_snapshot(selected_id)

    if detail is None:
        st.error(f"Snapshot #{selected_id} could not be found. The database may have changed.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Snapshot ID", detail["id"])
        col2.metric("Row Count", detail["row_count"])
        col3.metric("Uploaded At", detail["uploaded_at"])

        st.caption(f"Source file: {detail['source_filename'] or '(unknown)'}")
        st.caption(f"Columns: {', '.join(detail['column_names'])}")

        st.dataframe(detail["dataframe"], use_container_width=True)
