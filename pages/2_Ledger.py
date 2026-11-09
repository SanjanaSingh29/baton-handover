"""The claim ledger: every claim with its evidence status, plus a timeline."""
import streamlit as st

import db
import handover
import state
import ui
from config import CLAIM_TYPES, STATUSES

st.set_page_config(page_title="Ledger - Baton", layout="wide")
db.init_db()
ui.apply_theme()

st.title("2. Claim ledger")
st.caption("Everything Baton found, with how well each statement is supported.")

case = state.current_case()
if case is None:
    st.info("Create a case first on the Case Setup page.")
    st.stop()

claims = db.list_claims(case["id"])
if not claims:
    st.info("Nothing here yet. Build the handover on the Case Setup page.")
    st.page_link("pages/1_Case_Setup.py", label="Go to Case Setup")
    st.stop()

counts = {s: sum(1 for c in claims if c["status"] == s) for s in STATUSES}
colors = {"Verified": "green", "Inferred": "purple", "Conflicting": "amber", "Missing": "coral", "Unverified": "pink"}
cols = st.columns(len(STATUSES))
for col, status in zip(cols, STATUSES):
    with col:
        ui.metric_tile(status, counts[status], colors[status])

f1, f2 = st.columns(2)
type_filter = f1.multiselect("Claim types", CLAIM_TYPES, default=CLAIM_TYPES)
status_filter = f2.multiselect("Statuses", STATUSES, default=STATUSES)
shown = [c for c in claims if c["claim_type"] in type_filter and c["status"] in status_filter]

sources = {s["id"]: s["filename"] for s in db.list_sources(case["id"])}
left, right = st.columns([2, 1])
with left:
    rows = ""
    for c in shown:
        where = sources.get(c["source_id"], "no source")
        left_html = (
            f'{ui.esc(c["statement"])}<br><span class="baton-small">'
            f'{ui.esc(c["claim_type"])} | {ui.esc(where)}</span>'
        )
        right_html = ui.badge(c["status"]) + " " + ui.sensitivity_badge(c["sensitivity"])
        rows += ui.row(left_html, right_html)
    ui.tile(f"Claims ({len(shown)})", rows or "No claims match the filters.", "mint")
with right:
    events = handover.build_timeline(claims, db.get_chunk)
    body = "".join(
        ui.row(f'<b>{ui.esc(day)}</b><br>{ui.esc(c["statement"])}') for day, c in events
    )
    ui.tile("Timeline", body or "No dated events found.", "amber")

st.page_link("pages/3_Review.py", label="Review and approve the claims")