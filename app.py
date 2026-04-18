"""GTM Coach prototype.

Run with:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...
    streamlit run app.py
"""

import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from brief_layout import compute_brief_metrics, format_arr, parse_brief_sections
from db import save_brief, save_snapshot
from delta import compute_latest_delta, format_delta_for_brief
from validation import validate_columns

load_dotenv(Path(__file__).parent / ".env.local")

# In Streamlit Cloud the key lives in st.secrets, not as an env var.
# Locally it lives in .env.local. Try secrets first, then fall back to env.
if not os.environ.get("ANTHROPIC_API_KEY"):
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass  # st.secrets unavailable when running locally without secrets.toml

st.set_page_config(page_title="GTM Coach — Prototype", layout="wide")
st.title("GTM Coach — Prototype")
st.caption("Upload a territory export. Get coached, not filtered.")

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error(
        "ANTHROPIC_API_KEY not found. Set it in `.env.local` (local) or "
        "Streamlit Cloud secrets (deployed)."
    )
    st.stop()

PLAYBOOK = Path(__file__).parent.joinpath("system_prompt.md").read_text()

uploaded = st.file_uploader(
    "Drop your Salesforce territory export (.xlsx or .csv)",
    type=["xlsx", "csv"],
)

rep_context = st.text_area(
    "Anything else the coach should know? Call notes, deals you're worried about, what you want help thinking through.",
    placeholder=(
        "e.g. 'Acme renewal in 60 days, CSM went silent. "
        "Worried about Globex — they hinted at consolidating vendors.'"
    ),
    height=120,
)

if st.button("Coach me", disabled=not uploaded, type="primary"):
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    # ── Pre-flight validation (before LLM call) ────────────────────────────
    validation = validate_columns(df.columns.tolist())
    for warning in validation["warnings"]:
        st.warning(warning)

    snapshot_id, snapshot_timestamp, snapshot_is_new = save_snapshot(df, uploaded.name)
    if not snapshot_is_new:
        st.info(
            f"Identical to your last upload (snapshot #{snapshot_id}, saved {snapshot_timestamp}). "
            "Coaching anyway, but no new snapshot was saved — make sure you actually edited and saved the file before re-uploading."
        )

    # ── Delta detection (after snapshot saved) ─────────────────────────────
    delta = compute_latest_delta()
    delta_section = ""
    if delta is not None:
        delta_section = format_delta_for_brief(delta)

    territory_md = df.to_markdown(index=False)
    summary = f"Rows: {len(df)} | Columns: {', '.join(df.columns.tolist())}"

    # ── Build user_message with optional sections ──────────────────────────
    # Section order: Summary → What Changed (if any) → Territory Data →
    #                Data Quality (if any) → Rep's Context
    data_quality_section = ""
    if validation["warnings"]:
        warnings_md = "\n".join(f"- {w}" for w in validation["warnings"])
        data_quality_section = f"\n## Data Quality\n{warnings_md}\n"

    changed_section = f"\n{delta_section}\n" if delta_section else ""

    user_message = f"""Here is the rep's territory export.

**Today's date: {date.today().isoformat()}** — calibrate the hiking trail (Red Zone = next 120 days, mid-term reviews = 4 months ago, etc.) against this date.

## Summary
{summary}
{changed_section}
## Territory Data
{territory_md}
{data_quality_section}
## Rep's Context
{rep_context.strip() if rep_context.strip() else '(none provided)'}
"""

    # ── At-a-glance metrics row (computed from snapshot, not from brief) ───
    metrics = compute_brief_metrics(df)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Accounts in territory", str(metrics["total_accounts"]))
    m2.metric("ARR at risk (next 120d)", format_arr(metrics["arr_at_risk"]))
    m3.metric(
        "Red Zone fires",
        str(metrics["red_zone_fires"]) if metrics["red_zone_fires"] is not None else "—",
    )
    m4.metric(
        "Days to next renewal",
        str(metrics["days_to_next_renewal"]) if metrics["days_to_next_renewal"] is not None else "—",
    )

    client = Anthropic()
    placeholder = st.empty()
    accumulated = ""

    with st.spinner("Thinking through your territory..."):
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=64000,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=[
                {
                    "type": "text",
                    "text": PLAYBOOK,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                accumulated += text
                # Escape $ so Streamlit's markdown renderer doesn't trigger
                # MathJax/LaTeX mode on dollar amounts ("$1.1M ... $610K" etc.)
                placeholder.markdown(accumulated.replace("$", "\\$"))

            final = stream.get_final_message()

    # ── Persist the brief so the rep can revisit it later ──────────────────
    brief_id, brief_generated_at = save_brief(
        snapshot_id=snapshot_id,
        brief_text=accumulated,
        rep_context=rep_context.strip() if rep_context.strip() else None,
        model="claude-sonnet-4-6",
        input_tokens=final.usage.input_tokens,
        output_tokens=final.usage.output_tokens,
        cache_read_tokens=final.usage.cache_read_input_tokens,
    )

    # ── Replace the streaming placeholder with structured sections ─────────
    sections = parse_brief_sections(accumulated)
    with placeholder.container():
        for section in sections:
            with st.container(border=True):
                if section["heading"]:
                    if section["kind"] == "headline":
                        st.markdown(f"### 📌 {section['heading']}")
                    else:
                        st.markdown(f"### {section['heading']}")
                st.markdown(section["body"].replace("$", "\\$"))

    st.divider()
    with st.expander("Run details"):
        usage = final.usage
        st.write(f"Brief ID: {brief_id}  (saved at {brief_generated_at})")
        st.write(f"Snapshot ID: {snapshot_id}  (saved at {snapshot_timestamp})")
        st.write(f"Input tokens: {usage.input_tokens}")
        st.write(f"Cache read: {usage.cache_read_input_tokens}")
        st.write(f"Cache create: {usage.cache_creation_input_tokens}")
        st.write(f"Output tokens: {usage.output_tokens}")
        st.write(f"Stop reason: {final.stop_reason}")
