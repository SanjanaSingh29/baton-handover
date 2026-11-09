"""Step 1 and 2 of the workflow: connect sources, then build the handover."""
import streamlit as st

import db
import extractor
import parsers
import state
import ui
from config import BASE_DIR, ROLES, SENSITIVITIES

st.set_page_config(page_title="Case setup - Baton", layout="wide")
db.init_db()
ui.apply_theme()

DEMO_DIR = BASE_DIR / "demo_data"
DEMO_SOURCES = [
    ("meeting_notes.md", "Team"),
    ("club_chat.json", "Team"),
    ("tasks.csv", "Open"),
    ("finance_note.md", "Restricted"),
]
INCOMING_ROLES = [r for r in ROLES if r != "Project Lead"]


def add_sources(case_id, files):
    """files is a list of (filename, raw_bytes, sensitivity). Returns a list of error messages."""
    errors = []
    added = []
    for name, raw, sensitivity in files:
        try:
            text, chunks = parsers.parse_file(name, raw)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        source_id = db.add_source(case_id, name, sensitivity, text)
        db.add_chunks(source_id, chunks)
        added.append(name)
    if added:
        db.log_action(case_id, "sources_added", ", ".join(added))
    return errors


st.title("1. Case setup")
st.caption("Create a handover case, add authorised sources, and tag how sensitive each one is.")
st.warning(
    "Only add synthetic, public, anonymised or permissioned material. "
    "Do not upload confidential files you have no permission to use."
)

left, right = st.columns(2)
with left:
    with st.form("new_case"):
        st.subheader("New handover case")
        title = st.text_input("Project name", placeholder="Campus Fest app")
        leaver = st.text_input("Person leaving", placeholder="Aarav")
        role = st.selectbox("Successor's role", INCOMING_ROLES)
        if st.form_submit_button("Create case", type="primary"):
            if not title.strip() or not leaver.strip():
                st.error("Please enter the project name and the person leaving.")
            else:
                new_id = db.create_case(title.strip(), leaver.strip(), role)
                db.log_action(new_id, "case_created", title.strip())
                st.session_state["case_id"] = new_id
                st.rerun()
with right:
    st.subheader("Demo project")
    ui.tile(
        "Synthetic club project",
        "A made-up student club app with meeting notes, a chat export, a task board and a "
        "restricted finance note. It includes planted conflicts and gaps so every step can be tried.",
        "purple",
    )
    if st.button("Create the demo case"):
        demo_id = db.create_case("Campus Fest app handover", "Aarav", "Incoming Developer")
        files = [(name, (DEMO_DIR / name).read_bytes(), level) for name, level in DEMO_SOURCES]
        add_sources(demo_id, files)
        db.log_action(demo_id, "case_created", "demo project")
        st.session_state["case_id"] = demo_id
        st.rerun()

case = state.current_case()
if case is None:
    st.info("Create a case or the demo case to begin.")
    st.stop()

st.divider()
st.subheader(f'Case #{case["id"]}: {case["title"]}')
st.caption(f'Person leaving: {case["leaver"]}  |  Successor role: {case["successor_role"]}  |  Status: {case["status"]}')

# ----- add sources -----
st.markdown("#### Add sources")
uploads = st.file_uploader(
    "Meeting notes, chat exports, task boards (.md, .txt, .csv, .json)",
    type=["md", "txt", "csv", "json"],
    accept_multiple_files=True,
)
chosen = []
for f in uploads or []:
    c1, c2 = st.columns([3, 1])
    c1.write(f.name)
    level = c2.selectbox("Sensitivity", SENSITIVITIES, index=1, key=f"sens_{case['id']}_{f.name}")
    chosen.append((f.name, f.getvalue(), level))
if chosen and st.button("Add these sources"):
    problems = add_sources(case["id"], chosen)
    for p in problems:
        st.error(p)
    if not problems:
        st.rerun()

sources = db.list_sources(case["id"])
if sources:
    rows = ""
    for s in sources:
        n_chunks = len(db.list_chunks(s["id"]))
        rows += ui.row(f'{ui.esc(s["filename"])} <span class="baton-small">({n_chunks} chunks)</span>',
                       ui.sensitivity_badge(s["sensitivity"]))
    ui.tile(f"Sources in this case ({len(sources)})", rows, "mint")
else:
    st.info("No sources yet. Upload files above, or create the demo case.")

# ----- build -----
st.markdown("#### Build the handover")
existing = db.list_claims(case["id"])
if existing:
    st.warning("Building again replaces the current claims and your review decisions.")

mode = st.radio(
    "How should Baton read the sources?",
    ["AI extraction (Gemini)", "Saved sample output (demo project only)"],
)
if st.button("Build handover", type="primary", disabled=not sources):
    use_cached = mode.startswith("Saved")
    try:
        with st.spinner("Reading sources and checking every quote..."):
            summary = extractor.run_extraction(case["id"], use_cached=use_cached)
    except extractor.LLMUnavailable as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Something went wrong while building: {exc}")
    else:
        st.success(
            f'Built {summary["total"]} claims: {summary["Verified"]} verified, '
            f'{summary["Inferred"]} inferred, {summary["Conflicting"]} conflicting, '
            f'{summary["Missing"]} missing, {summary["Unverified"]} unverified.'
        )
        if summary["skipped"]:
            st.info(f'{summary["skipped"]} unusable items from the AI were skipped.')
        st.page_link("pages/2_Ledger.py", label="Open the claim ledger")