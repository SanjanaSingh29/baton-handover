"""Acknowledgements, the activity log, the access audit, interview answers and claim versions."""
import pandas as pd
import streamlit as st

import audit
import db
import interview
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

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Access audit", "Acknowledgements", "Activity log", "Interview answers", "Claim versions"]
)

with tab1:
    rows = audit.list_access(case["id"])
    totals = audit.summarize(rows)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.metric_tile("Views", totals["views"], "mint")
    with c2:
        ui.metric_tile("PDF exports", totals["exports"], "purple")
    with c3:
        ui.metric_tile("Items held back", totals["hidden"], "coral", "Added up over all views")
    with c4:
        ui.metric_tile("Details masked", totals["redactions"], "pink", "Added up over all views")
    st.caption(
        "The viewer is the role chosen in the demo. There is no sign-in, so this shows which role "
        "opened or exported the handover, how much was shown, and how much was held back."
    )
    if rows:
        table = pd.DataFrame(rows)[["created_at", "role", "action", "items_shown", "items_hidden", "redactions"]]
        table.columns = ["When (UTC)", "Role", "Action", "Shown", "Hidden", "Masked"]
        st.dataframe(table, hide_index=True)
    else:
        st.info("Nobody has opened the handover yet.")

with tab2:
    acks = db.list_acknowledgements(case["id"])
    if acks:
        st.dataframe(pd.DataFrame(acks)[["name", "role", "acknowledged_at"]], hide_index=True)
    else:
        st.info("Nobody has acknowledged the handover yet.")

with tab3:
    log = db.list_audit(case["id"])
    if log:
        st.dataframe(pd.DataFrame(log)[["created_at", "action", "detail"]], hide_index=True)
    else:
        st.info("No activity yet.")

with tab4:
    answers = list(interview.list_answers(case["id"]).values())
    if answers:
        st.dataframe(
            pd.DataFrame(answers)[["created_at", "question", "answer", "answered_by", "sensitivity"]],
            hide_index=True,
        )
    else:
        st.info("The gap interview has no answers yet.")

with tab5:
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