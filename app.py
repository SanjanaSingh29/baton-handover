import streamlit as st

import db
import ui

st.set_page_config(page_title="Baton", layout="wide")
db.init_db()
ui.apply_theme()

st.session_state.setdefault("case_id", None)

st.title("Baton")
st.caption("Evidence-linked project handovers, shared only with the people allowed to see them.")

stats = db.counts()
c1, c2, c3 = st.columns(3)
with c1:
    ui.metric_tile("Handover cases", stats["cases"], "mint")
with c2:
    ui.metric_tile("Sources imported", stats["sources"], "coral")
with c3:
    ui.metric_tile("Claims in the ledger", stats["claims"], "purple")

left, right = st.columns([2, 1])
with left:
    ui.tile(
        "How Baton works",
        ui.row("1. Connect authorised sources", ui.badge("Open", ui.SENSITIVITY_COLORS))
        + ui.row("2. Reconstruct decisions, owners and risks")
        + ui.row("3. Verify every claim against its quote", ui.badge("Verified"))
        + ui.row("4. Review and approve as the lead")
        + ui.row("5. Hand over a role-based view"),
        "pink",
    )
with right:
    ui.tile(
        "Statuses",
        ui.row("Quote found in source", ui.badge("Verified"))
        + ui.row("Reasoned from clues", ui.badge("Inferred"))
        + ui.row("Sources disagree", ui.badge("Conflicting"))
        + ui.row("Nothing supports it", ui.badge("Missing")),
        "amber",
    )

st.info("Step 1 complete: the app, database and theme are working. Next step: demo data and file parsing.")