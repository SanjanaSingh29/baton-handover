"""Acknowledgements, the activity log and the version history of every claim."""
import pandas as pd
import streamlit as st

import db
import state
import ui

st.set_page_config(page_title="History - Baton", layout="wide")
db.init_db()
ui.apply_theme()

st.title("5. History")

case = state.current_case()
if case is None:
    st.info("Create a case first on the Case Setup page.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Acknowledgements", "Activity log", "Claim versions"])

with tab1:
    acks = db.list_acknowledgements(case["id"])
    if acks:
        st.dataframe(pd.DataFrame(acks)[["name", "role", "acknowledged_at"]], hide_index=True)
    else:
        st.info("Nobody has acknowledged the handover yet.")

with tab2:
    log = db.list_audit(case["id"])
    if log:
        st.dataframe(pd.DataFrame(log)[["created_at", "action", "detail"]], hide_index=True)
    else:
        st.info("No activity yet.")

with tab3:
    rows = []
    for c in db.list_claims(case["id"]):
        for v in db.list_claim_versions(c["id"]):
            rows.append({
                "claim": c["id"], "version": v["version"], "statement": v["statement"],
                "by": v["edited_by"], "when": v["created_at"], "note": v["note"],
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    else:
        st.info("No claims yet.")