"""Gap interview: questions for the person leaving, built from the gaps and conflicts found."""
import streamlit as st

import db
import interview
import state
import ui
from config import SENSITIVITIES

st.set_page_config(page_title="Interview - Baton", layout="wide")
db.init_db()
interview.ensure_tables()
ui.apply_theme()

st.title("6. Gap interview")
st.caption(
    "Baton found gaps, conflicts and unsupported statements. Answer them here. Answers are saved as "
    "evidence stated by the person leaving, kept separate from claims verified in project files, "
    "and they still need the project lead's approval in Review."
)

case = state.current_case()
if case is None:
    st.info("Create a case first on the Case Setup page.")
    st.stop()

claims = db.list_claims(case["id"])
if not claims:
    st.info("Nothing to ask yet. Build the handover on the Case Setup page.")
    st.page_link("pages/1_Case_Setup.py", label="Go to Case Setup")
    st.stop()

questions = interview.build_questions(claims)
answers = interview.list_answers(case["id"])
existing_ids = {c["id"] for c in claims}
done = sum(1 for q in questions if interview.is_answered(answers.get(q["key"]), existing_ids))

m1, m2 = st.columns(2)
with m1:
    ui.metric_tile("Questions", len(questions), "pink")
with m2:
    ui.metric_tile("Answered", done, "green", f"{len(questions) - done} still open")

if not questions:
    st.success("No gaps, conflicts or unsupported statements were found, so there is nothing to ask.")
    st.stop()

for index, q in enumerate(questions):
    answer = answers.get(q["key"])
    answered = interview.is_answered(answer, existing_ids)
    label = {"conflict": "Conflict", "missing_owner": "Gap", "missing_contact": "Gap", "unverified": "Unsupported"}[q["kind"]]
    badge = ui.badge("Stated") if answered else ui.badge({"Conflict": "Conflicting", "Gap": "Missing", "Unsupported": "Unverified"}[label])
    ui.tile(f"Question {index + 1}: {label}", f'<div style="font-size:15px;margin-bottom:6px">{ui.esc(q["text"])}</div>{badge}', "amber" if not answered else "green")

    previous = answer["choice"] if answer else ""
    with st.form(f"question_{index}"):
        other = ""
        if q["kind"] == "conflict":
            options = q["options"] + [interview.OTHER_LABEL]
            start = options.index(previous) if previous in options else (len(options) - 1 if previous else 0)
            choice = st.radio("Which is correct?", options, index=start, key=f"choice_{index}")
            other = st.text_input("If something else, what is the correct answer?", value=previous if previous not in options else "", key=f"other_{index}")
        elif q["kind"] == "unverified":
            start = q["options"].index(previous) if previous in q["options"] else 1
            choice = st.radio("Is this true?", q["options"], index=start, key=f"choice_{index}")
        else:
            choice = st.text_input("Name", value=previous, key=f"choice_{index}", placeholder="For example: Meera")
        note = st.text_area("Anything the successor should know? (optional)", value=answer["note"] if answer and answer["note"] else "", key=f"note_{index}")
        c1, c2 = st.columns(2)
        who = c1.text_input("Answered by", value=answer["answered_by"] if answer else case["leaver"], key=f"who_{index}")
        sensitivity = c2.selectbox(
            "Who may see this answer?", SENSITIVITIES,
            index=SENSITIVITIES.index(answer["sensitivity"]) if answer else 1, key=f"sens_{index}",
        )
        if st.form_submit_button("Update answer" if answered else "Save answer", type="primary"):
            try:
                interview.save_answer(case["id"], q, choice, other, note, who, sensitivity, case["leaver"])
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.rerun()

st.divider()
st.page_link("pages/3_Review.py", label="Next: review and approve the claims")