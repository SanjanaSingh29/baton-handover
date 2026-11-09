"""Step 4: the lead checks each claim against its evidence, then approves the handover."""
import streamlit as st

import db
import state
import ui
import verifier

st.set_page_config(page_title="Review - Baton", layout="wide")
db.init_db()
ui.apply_theme()

st.title("3. Review")
st.caption("Check each claim beside its evidence. Nothing is shared until you approve.")

case = state.current_case()
if case is None:
    st.info("Create a case first on the Case Setup page.")
    st.stop()

claims = db.list_claims(case["id"])
if not claims:
    st.info("Nothing to review yet. Build the handover on the Case Setup page.")
    st.stop()

# Problem claims first, so the lead sees the risky ones early.
PRIORITY = {"Conflicting": 0, "Missing": 1, "Unverified": 2, "Inferred": 3, "Verified": 4}
claims.sort(key=lambda c: (PRIORITY.get(c["status"], 5), c["id"]))

n_acc = sum(1 for c in claims if c["review_state"] == "accepted")
n_rej = sum(1 for c in claims if c["review_state"] == "rejected")
n_pen = len(claims) - n_acc - n_rej
m1, m2, m3 = st.columns(3)
with m1:
    ui.metric_tile("Accepted", n_acc, "green")
with m2:
    ui.metric_tile("Rejected", n_rej, "coral")
with m3:
    ui.metric_tile("Still to review", n_pen, "amber")

key = f"review_idx_{case['id']}"
idx = min(st.session_state.get(key, 0), len(claims) - 1)
claim = claims[idx]

nav1, nav2, nav3 = st.columns([1, 2, 1])
if nav1.button("Previous", disabled=idx == 0):
    st.session_state[key] = idx - 1
    st.rerun()
nav2.markdown(f"**Claim {idx + 1} of {len(claims)}**")
if nav3.button("Next", disabled=idx >= len(claims) - 1):
    st.session_state[key] = idx + 1
    st.rerun()

sources = {s["id"]: s for s in db.list_sources(case["id"])}
source = sources.get(claim["source_id"])
state_label = {"pending": "Not reviewed yet", "accepted": "Accepted", "rejected": "Rejected"}[claim["review_state"]]

col_claim, col_evidence = st.columns(2)
with col_claim:
    body = (
        f'<div style="font-size:16px;margin-bottom:8px">{ui.esc(claim["statement"])}</div>'
        f'{ui.badge(claim["status"])} {ui.sensitivity_badge(claim["sensitivity"])}'
        f'<div class="baton-small" style="margin-top:8px">Type: {ui.esc(claim["claim_type"])} | '
        f'Subject: {ui.esc(claim["subject"] or "none")} | Value: {ui.esc(claim["value"] or "none")}<br>'
        f'Review: {state_label} | Version {claim["version"]}</div>'
    )
    ui.tile("Claim", body, "pink")

    if claim["status"] == "Conflicting":
        others = [
            o for o in claims
            if o["id"] != claim["id"] and o["status"] == "Conflicting"
            and verifier.same_subject(o["subject"], claim["subject"])
        ]
        rows = "".join(
            ui.row(ui.esc(o["statement"]), ui.esc(o["value"] or "")) for o in others
        )
        ui.tile("Other versions that disagree", rows or "No other versions found.", "amber")
    elif claim["status"] == "Unverified":
        st.warning("No supporting quote was found in any source. Unverified claims are never published in a handover, so reject this one, or fix the source and build again.")
    elif claim["status"] == "Missing":
        st.info("Baton found no source for this. Accept it if the gap is real and the successor should know about it.")
    elif claim["status"] == "Inferred":
        st.info("This is Baton's reasoning from the quote shown. It is an assumption, not a stated fact.")

with col_evidence:
    if claim["status"] == "Missing":
        ui.tile("Evidence", "Nothing supports this item. That is the point: the information is missing.", "coral")
    elif claim["status"] == "Unverified":
        ui.tile(
            "Evidence",
            f'The quote the AI gave was not found in any source:<br><i>{ui.esc(claim["quote"])}</i>',
            "coral",
        )
    elif source and claim["chunk_index"] is not None:
        chunk = db.get_chunk(source["id"], claim["chunk_index"])
        text = verifier.highlight(chunk["text"], claim["quote"]) if chunk else "Source text not found."
        body = (
            f'<div class="baton-small">{ui.esc(source["filename"])}, chunk {claim["chunk_index"]} '
            f'{ui.sensitivity_badge(source["sensitivity"])}</div>'
            f'<div style="margin-top:8px;line-height:1.6">{text}</div>'
        )
        ui.tile("Source evidence", body, "mint")

b1, b2, b3 = st.columns(3)
if b1.button("Accept", key=f"acc_{claim['id']}", type="primary"):
    db.set_review_state(claim["id"], "accepted")
    db.log_action(case["id"], "claim_accepted", f'#{claim["id"]}')
    if idx < len(claims) - 1:
        st.session_state[key] = idx + 1
    st.rerun()
if b2.button("Reject", key=f"rej_{claim['id']}"):
    db.set_review_state(claim["id"], "rejected")
    db.log_action(case["id"], "claim_rejected", f'#{claim["id"]}')
    if idx < len(claims) - 1:
        st.session_state[key] = idx + 1
    st.rerun()
if b3.button("Reset to not reviewed", key=f"rst_{claim['id']}"):
    db.set_review_state(claim["id"], "pending")
    st.rerun()

with st.expander("Edit this claim"):
    new_text = st.text_area("Statement", value=claim["statement"], key=f"edit_{claim['id']}_{claim['version']}")
    if st.button("Save edit", key=f"save_{claim['id']}"):
        if new_text.strip() and new_text.strip() != claim["statement"]:
            db.edit_claim(claim["id"], new_text.strip())
            db.log_action(case["id"], "claim_edited", f'#{claim["id"]}')
            st.rerun()
        else:
            st.info("Change the text first.")

with st.expander("Version history"):
    for v in db.list_claim_versions(claim["id"]):
        st.markdown(f'**v{v["version"]}** by {v["edited_by"]} ({v["created_at"]} UTC): {v["statement"]}')

st.divider()
st.subheader("Approve and publish")
st.caption("Only accepted claims go into the handover. Each role then sees only what it is allowed to see.")
if case["status"] == "approved":
    st.success("This handover is published.")
    if st.button("Unpublish"):
        db.set_case_status(case["id"], "extracted")
        db.log_action(case["id"], "unpublished")
        st.rerun()
else:
    if n_pen:
        st.warning(f"{n_pen} claims are still not reviewed. They will be left out of the handover.")
    if st.button("Approve and publish handover", type="primary", disabled=n_acc == 0):
        db.set_case_status(case["id"], "approved")
        db.log_action(case["id"], "published", f"{n_acc} claims")
        st.rerun()
st.page_link("pages/4_Role_View.py", label="Open the role view")