# Baton

Evidence-linked project handovers. Baton turns scattered project files into a reviewable
handover. Every statement links to an exact quote, is marked **Verified**, **Inferred**,
**Conflicting** or **Missing**, and is shared only with the roles allowed to see it.

Built for the CodersInPune Hackathon (Round 2) by team **ROOT CAUSE** (Sanjana Singh, solo).

**Live app:** _add your Streamlit link here after deployment_

## The problem

When someone leaves a project, the reasons behind decisions, unfinished work, risks and who to
ask are lost in chats, issues and notes. A normal summary cannot be trusted because it does not
show which statements are supported, and it may expose material the successor should not see.

## How it works

1. **Connect:** upload meeting notes, chat exports (.json), task boards (.csv) and text files, and tag each source Open, Team or Restricted.
2. **Reconstruct:** an AI model proposes claims (decisions, owners, open tasks, risks, dependencies, contacts, recurring problems), each with an exact quote and a source.
3. **Verify:** plain Python checks that every quote exists in the cited source. The AI cannot mark its own claims verified. Conflicts and missing items are found by code, not by the AI.
4. **Review:** the project lead accepts, edits or rejects each claim. Every edit is saved as a new version.
5. **Handover:** the lead publishes. Each role sees only claims at or below its sensitivity level, with a first-week plan, evidence for each statement, and an acknowledge-receipt step.

### Evidence statuses

| Status | Meaning |
| --- | --- |
| Verified | The exact quote was found in a source |
| Inferred | The AI's reasoning from a verified clue, shown as an assumption |
| Conflicting | Sources disagree about the same thing; both versions are kept |
| Missing | A checklist item has no source (an open task with no owner, a dependency with no contact) |
| Unverified | No supporting quote was found. Never published in a handover |

### Roles (demo)

| Role | Sees |
| --- | --- |
| Project Lead | Open, Team, Restricted |
| Incoming Developer | Open, Team |
| Incoming Volunteer | Open |

The role switcher is for the demo. A production version would use real sign-in.

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

Then open **Case Setup**, click **Create the demo case**, choose **Saved sample output**, and click **Build handover**.

### Using the live AI

1. Get a Gemini API key from Google AI Studio.
2. Copy `.env.example` to `.env` and put your key in it. Never commit `.env`.
3. Optional: set `LLM_MODEL` in `.env` if the default model name is retired.
4. On Case Setup, choose **AI extraction (Gemini)**.

## Demo data and saved sample output

- Everything in `demo_data/` is **synthetic**: a made-up student club project.
- It includes planted conflicts, gaps, a restricted finance note and one invented claim, so every feature has something to catch.
- `demo_data/cached_claims.json` is a **saved sample output**, not a live AI call. It lets the demo run without an API key. Its last claim ("move hosting to AWS") is deliberately unsupported so you can watch the verifier catch it.
- Do not upload confidential material you have no permission to use.

## Status

**Working now (Round 2):** file import, claim extraction with exact quotes, automatic quote verification, conflict detection, missing-item checklist, review (accept, edit, reject) with version history, role-based handover with sensitivity filtering, first-week plan, acknowledgement of receipt, activity log.

**Planned for Round 3:**
1. Evidence-driven gap interview: turn Missing and Conflicting items into short questions for the person leaving, saved as attributed evidence.
2. Redaction of sensitive details inside sources, plus an access audit view.
3. Export of the approved handover as a PDF.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Technology

Python, Streamlit, SQLite, pandas,