"""Brief History page — list and re-read past briefs.

Each brief is linked to the snapshot it was generated from, so the rep can
trace "what I was looking at" alongside "what the coach said."
"""

from datetime import date, datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from brief_layout import parse_brief_sections
from db import get_brief, get_briefs

load_dotenv(Path(__file__).parent.parent / ".env.local")

st.set_page_config(page_title="Brief History — GTM Coach", layout="wide")
st.title("Brief History")
st.caption("Past coaching briefs. Click any one to re-read.")

briefs = get_briefs()

if not briefs:
    st.info(
        "No briefs generated yet. Head to the main page, upload a territory, "
        "and click 'Coach me' — your first brief will appear here."
    )
    st.stop()

# ── Brief picker ─────────────────────────────────────────────────────────

def _label(b: dict) -> str:
    when = b["generated_at"]
    # Friendlier date if we can parse it
    try:
        when = datetime.fromisoformat(b["generated_at"]).strftime("%b %d, %Y · %H:%M")
    except Exception:
        pass
    snippet = f" · context: {b['rep_context'][:60]}…" if b.get("rep_context") else ""
    return f"#{b['id']}  ·  {when}  ·  snapshot #{b['snapshot_id']}{snippet}"


choice = st.selectbox(
    "Pick a brief to re-read",
    options=briefs,
    format_func=_label,
    index=0,
)

st.divider()

# ── Render the selected brief in the same structured layout as the main page ──

full = get_brief(choice["id"])
if full is None:
    st.error("Brief not found — this shouldn't happen. Try refreshing.")
    st.stop()

# Header strip with metadata
left, right = st.columns([3, 1])
with left:
    st.markdown(f"### Brief #{full['id']}")
    st.caption(
        f"Generated {full['generated_at']} · from snapshot #{full['snapshot_id']}"
        + (f" · model {full['model']}" if full.get("model") else "")
    )
    if full.get("rep_context"):
        with st.expander("Rep context provided at brief time"):
            st.markdown(full["rep_context"].replace("$", "\\$"))
with right:
    if full.get("output_tokens"):
        st.metric("Output tokens", full["output_tokens"])

st.divider()

sections = parse_brief_sections(full["brief_text"])
for section in sections:
    with st.container(border=True):
        if section["heading"]:
            if section["kind"] == "headline":
                st.markdown(f"### 📌 {section['heading']}")
            else:
                st.markdown(f"### {section['heading']}")
        st.markdown(section["body"].replace("$", "\\$"))
