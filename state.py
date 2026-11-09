"""Remembers which handover case is open while you move between pages."""
import streamlit as st

import db


def current_case():
    """Show the case picker in the sidebar and return the chosen case (or None)."""
    cases = db.list_cases()
    if not cases:
        return None
    ids = [c["id"] for c in cases]
    labels = {c["id"]: f'#{c["id"]} {c["title"]} (leaving: {c["leaver"]})' for c in cases}
    current = st.session_state.get("case_id")
    index = ids.index(current) if current in ids else 0
    chosen = st.sidebar.selectbox(
        "Handover case", ids, index=index, format_func=lambda i: labels[i]
    )
    st.session_state["case_id"] = chosen
    return db.get_case(chosen)