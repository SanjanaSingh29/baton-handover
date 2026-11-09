"""Step 5: the role-based handover, shown as a bento grid."""
import streamlit as st

import db
import handover
import permissions
import state
import ui
import verifier
from config import ROLES

st.set_page_config(page_title="Handover - Baton", layout="wide")
db.init_db()
ui.apply_theme()

st.title("4. Handover")

case = state.current_case()
if case is None:
    st.info("Create a case first on the Case Setup page.")
    st.stop()

role = st.selectbox(
    "View the handover as",
    list(ROLES),
    index=list(ROLES).index(case["successor_role"]) if case["successor_role"] in ROLES else 0,
)
st.caption("This role switcher is for the demo. A real deployment would use sign-in.")

if role != "Project Lead" and case["status"] != "approved":
    st.warning("This handover has not been approved yet. The project lead must approve it first.")
    st.stop()
if role == "Project Lead" and case["status"] != "approved":
    st.info("Preview: this handover is not published yet. Other roles cannot see it.")

accepted_all = db.list_claims(case["id"], review_state="accepted")
# Claims with no supporting quote are never published, even if the lead accepted them.
held_back = [c for c in accepted_all if c["status"] == "Unverified"]
accepted = [c for c in accepted_all if c["status"] != "Unverified"]
visible, hidden = permissions.split_by_role(accepted, role)
sources = {s["id"]: s for s in db.list_sources(case["id"])}


def of_type(*types):
    return [c for c in visible if c["claim_type"] in types and c["status"] != "Missing"]


def line(c):
    return ui.row(ui.esc(c["statement"]), ui.badge(c["status"]))


def value_cell(c, empty="No owner"):
    """A person or value, with a warning badge if the sources disagree about it."""
    text = ui.esc(c["value"]) if verifier.has_value(c["value"]) else empty
    return text + (" " + ui.badge("Conflicting") if c["status"] == "Conflicting" else "")


if held_back and role == "Project Lead":
    st.info(
        f"{len(held_back)} unverified claim(s) are held back and not shown in any handover. "
        "Reject them, or add the missing evidence and build again."
    )

st.subheader(f'{case["title"]}: handover from {case["leaver"]}')

top_left, top_right = st.columns([2, 1])
with top_left:
    plan = handover.build_plan(visible)
    body = "".join(
        ui.row(f'{i}. {ui.esc(step["text"])}', ui.badge(step["status"])) for i, step in enumerate(plan, 1)
    )
    ui.tile("Your first-week plan", body or "Nothing to plan yet.", "mint")
with top_right:
    ui.metric_tile("Hidden for your role", hidden, "pink", "Ask the project lead for access.")

c1, c2, c3 = st.columns(3)
with c1:
    tasks = of_type("open_task")
    body = "".join(ui.row(ui.esc(c["subject"]), value_cell(c)) for c in tasks)
    ui.tile("Open work", body or "None recorded.", "coral")
with c2:
    ui.tile("Risks and recurring problems", "".join(line(c) for c in of_type("risk", "recurring_problem")) or "None recorded.", "amber")
with c3:
    ask = [c for c in of_type("contact", "owner") if verifier.has_value(c["value"])]
    body = "".join(ui.row(ui.esc(c["subject"]), value_cell(c)) for c in ask)
    ui.tile("Who to ask", body or "None recorded.", "purple")

d1, d2 = st.columns([2, 1])
with d1:
    decisions = "".join(line(c) for c in of_type("decision"))
    events = handover.build_timeline(visible, db.get_chunk)
    timeline = "".join(ui.row(f'<b>{ui.esc(day)}</b> {ui.esc(c["statement"])}') for day, c in events)
    ui.tile("Decisions", decisions or "None recorded.", "green")
    ui.tile("Timeline", timeline or "No dated events.", "green")
with d2:
    gaps = [c for c in visible if c["status"] == "Missing"]
    ui.tile("Gaps to fill", "".join(line(c) for c in gaps) or "No gaps recorded.", "coral")
    dependencies = of_type("dependency")
    ui.tile("Dependencies", "".join(line(c) for c in dependencies) or "None recorded.", "purple")

st.markdown("#### Evidence behind each statement")
for c in visible:
    with st.expander(f'{c["statement"]}  [{c["status"]}]'):
        source = sources.get(c["source_id"])
        if c["status"] == "Missing":
            st.write("No source supports this item. It is listed because the information is missing.")
        elif source and c["chunk_index"] is not None:
            chunk = db.get_chunk(source["id"], c["chunk_index"])
            if chunk and c["status"] != "Unverified":
                ui.tile(
                    f'{source["filename"]}, chunk {c["chunk_index"]}',
                    verifier.highlight(chunk["text"], c["quote"]),
                    "mint",
                )
            else:
                st.write("The lead accepted this claim, but no quote could be matched to a source.")
        if c["status"] == "Inferred":
            st.caption("This is Baton's reasoning from the clue shown, not a stated fact.")

if role != "Project Lead":
    st.divider()
    st.subheader("Acknowledge receipt")
    name = st.text_input("Your name")
    if st.button("Acknowledge receipt", type="primary"):
        if name.strip():
            db.add_acknowledgement(case["id"], role, name.strip())
            db.log_action(case["id"], "acknowledged", f"{name.strip()} as {role}")
            st.success("Thank you. Your receipt has been recorded.")
        else:
            st.error("Please enter your name.")
    for a in db.list_acknowledgements(case["id"]):
        st.caption(f'{a["name"]} ({a["role"]}) acknowledged on {a["acknowledged_at"]} UTC')