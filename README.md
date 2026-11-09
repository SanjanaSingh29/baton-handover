# Baton

**Turn scattered project activity into a handover people can trust.**

Baton is a knowledge-handover web application built by team ROOT CAUSE for the CodersInPune Hackathon (We Code Coders). When someone leaves a project, Baton reads the project's own files, builds a ledger of decisions, owners, open work, risks and contacts, checks every statement against an exact quote from its source, and leaves the final decision to a person. Each role then sees only the claims it is allowed to see.

**Live app:** https://baton-root-cause.streamlit.app/
**Repository:** https://github.com/SanjanaSingh29/baton-handover
**Team:** ROOT CAUSE (solo participant: Sanjana Singh, Bhagwan Parshuram Institute of Technology)

## The problem

When a member leaves a project, the reasons behind decisions, unfinished work, owners, risks and contacts are usually lost. They sit in chats, issues, task boards and meeting notes. A normal summary cannot be trusted because it does not show which statements are supported, which are guesses and which conflict, and it may expose material the successor should not see.

## Try it (no setup needed)

Open the live app. If it shows a "wake up" button, click **Yes, get this app back up** and wait up to a minute. There are no accounts. Everything runs on a synthetic demo project, and the role is chosen from a dropdown.

Suggested path:

1. **Case Setup:** click **Create the demo case**. Four synthetic files are loaded and tagged Team, Team, Open and Restricted.
2. Choose **Saved sample output (demo project only)** and click **Build handover**.
3. **Ledger:** you should see 23 claims (15 Verified, 1 Inferred, 3 Conflicting, 3 Missing, 1 Unverified) and a timeline.
4. **Review:** problem claims come first. Open the login-bug owner conflict, read the other versions that disagree, and look at the highlighted source text. Find the claim "The club will move hosting to AWS next month": it is Unverified because no source contains its quote.
5. Accept the claims you want, then click **Approve and publish handover**. Unverified claims are never published, even if accepted.
6. **Handover:** view it as **Project Lead**, **Incoming Developer** and **Incoming Volunteer**. The restricted finance facts appear only for the lead, and "Hidden for your role" shows how many claims were held back.
7. As a successor role, enter a name and click **Acknowledge receipt**, then open **History** to see the acknowledgement, activity log and claim versions.

**About the demo data.** Everything in `demo_data/` is synthetic: a made-up student club project with planted conflicts, gaps, a restricted finance note and one invented claim, so every feature has something to catch. The **saved sample output** is a stored result, not a live AI call. Do not enter confidential material in the live app.

## How it works

1. **Connect:** upload meeting notes, chat exports, task boards and text files, and tag each source **Open**, **Team** or **Restricted**.
2. **Chunk:** each file is split into numbered chunks (one message per chunk for chats, one row per chunk for task boards). A chunk is the unit of evidence.
3. **Reconstruct:** an AI model (Google Gemini) reads the chunks and proposes claims: decisions, owners, open tasks, risks, dependencies, contacts and recurring problems. Each claim must include an exact quote, its source file and chunk.
4. **Verify (plain code, no AI):** a claim is kept as Verified only if its quote is found in a source. The check looks in the cited chunk, then the rest of that source, then the other sources, and records where the quote really is. The AI cannot mark its own claims verified.
5. **Conflicts and gaps (plain code):** claims about the same subject with different values are marked Conflicting and both versions are kept. A checklist creates Missing items: every open task needs an owner, every dependency needs a contact.
6. **Review:** the project lead accepts, rejects or edits each claim beside its highlighted source text. Every edit is saved as a new version.
7. **Handover:** the lead publishes. A permission filter runs in code before anything is shown, and the first-week plan is built only from claims the role may see.
8. **Acknowledge:** the successor confirms receipt, and the event is logged.

**Reliability:** the AI call retries up to three times. If the AI is unavailable, the app shows a clear message and the saved sample output still works. Items the AI returns in the wrong shape are skipped.

### Evidence statuses

| Status | Meaning |
| --- | --- |
| Verified | The exact quote was found in a source |
| Inferred | The AI's reasoning from a verified clue, shown as an assumption |
| Conflicting | Sources disagree about the same thing; both versions are kept |
| Missing | A checklist item has no source (an open task with no owner, a dependency with no contact) |
| Unverified | No supporting quote was found. Never published in a handover |

### Roles

| Role | Sees |
| --- | --- |
| Project Lead | Open, Team and Restricted claims |
| Incoming Developer | Open and Team claims |
| Incoming Volunteer | Open claims only |

A claim takes the sensitivity of the source its quote was found in. A claim with no known source is treated as Restricted until a person decides.

## Features

- Import of `.md`, `.txt`, `.csv` and chat `.json` files with per-source sensitivity tags
- AI claim extraction with exact quotes, plus a saved sample output for the demo
- Quote verification by plain code, with correction of wrong file or chunk citations
- Five evidence statuses shown as colour badges that also carry the status word
- Conflict detection for owners, tasks, decisions and contacts
- Missing-item checklist (task without owner, dependency without contact)
- Claim ledger with filters and a timeline built from dated chat messages
- Review screen: accept, reject or edit, with the claim beside its highlighted evidence
- Version history for every claim
- Publish and unpublish; only accepted, verified claims reach a handover
- Role-based handover as a colourful bento grid: first-week plan, open work, risks, who to ask, decisions, timeline, gaps, dependencies and an evidence panel
- Hidden-item count so a role knows something was withheld
- Acknowledgement of receipt, activity log and history page
- Output from files and the AI is HTML-escaped before display
- Automated tests (17) covering parsers, verifier, permissions and the full demo flow

## File formats

| File | What Baton expects |
| --- | --- |
| `.md`, `.txt` | Plain text. Split into paragraph chunks. |
| `.csv` | A header row plus rows, for example `task,owner,status,due`. A blank owner becomes "(not assigned)". |
| `.json` | A chat export such as `{"messages": [{"time": "2026-10-03 18:20", "author": "Aarav", "text": "..."}]}`. One message per chunk. |

The whole prompt is limited to about 80,000 characters.

## Technology

| Part | Choice |
| --- | --- |
| App and UI | Python, Streamlit |
| Database | SQLite (Python standard library) |
| AI | Google Gemini through the `google-genai` SDK; the model name is configurable with `LLM_MODEL` |
| Checks | Plain Python: quote matching, conflict detection, missing-item checklist, permission filter |
| Data views | pandas |
| Configuration | python-dotenv |
| Hosting | Streamlit Community Cloud, GitHub |

## Project structure

```
app.py                    Home
pages/                    Case Setup, Ledger, Review, Role View, History
parsers.py                Reads files and creates numbered chunks
extractor.py              Prompt, Gemini call, input checks, runs verification
verifier.py               Quote matching, highlighting, conflicts, missing items
permissions.py            Role to sensitivity filter
handover.py               First-week plan and timeline (no AI)
db.py                     SQLite tables and queries
state.py                  Remembers the open case between pages
ui.py, config.py          Shared theme, tiles, badges and settings
demo_data/                Synthetic demo files and the saved sample output
tests/                    Automated tests
```

## AI use and disclosure

- **Inside the product:** Google Gemini proposes claims. The text of the uploaded sources is sent to Google's API when live AI extraction is used.
- **During development:** Claude (Anthropic) helped plan the project and write and explain parts of the code, the demo data and the documents. The author reviewed and ran the work.
- **Libraries:** Streamlit, google-genai, python-dotenv, pandas and the Python standard library.
- **Development window:** development of this project started when the Round 2 window opened. Earlier work was research and planning only.

## Limitations

- There is one project workspace and no sign-in. The role is chosen from a dropdown, so anyone using the app can act as the project lead. A real deployment would use authenticated accounts, and the same person should not review and approve their own handover.
- The database is a local SQLite file. On Streamlit Community Cloud it can reset after a sleep or restart, so a case you created may disappear. Use **Create the demo case** to recreate the demo.
- Each claim cites one quote from one source. A claim reasoned from several sources is not yet supported, and a quote spanning two chunks is marked Unverified.
- Sensitivity is tagged by hand per source, a simplification of real organisational permissions.
- Conflict detection compares claim subjects by word overlap and can miss or over-flag cases, so the lead reviews every claim.
- AI claims are not always right. Verification proves that the quote exists, not that the AI's reasoning is correct, which is why people make the final decision.
- Only text files are supported. PDF, Word and image files are not.
- Do not enter confidential material in the live app.

## Roadmap

**Round 3 (planned):**
1. **Evidence-driven gap interview:** turn every Missing and Conflicting item into a short question for the person leaving, saved as dated, attributed evidence kept separate from source-verified claims.
2. **Redaction and access audit:** mask sensitive details such as emails, phone numbers and payment amounts inside sources for roles without access, and add an audit view of who viewed and acknowledged each handover.
3. **Handover export:** export the approved, role-specific handover as a PDF.

**Later:** real sign-in and workspaces, live connectors for GitHub, Google Drive and chat platforms, a handover that updates weekly instead of only at departure, coverage reports showing areas that depend on one person, and an optional local model for teams that cannot send data to an external service.

## Run locally

```bash
git clone https://github.com/SanjanaSingh29/baton-handover.git
cd baton-handover
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

To use live AI extraction, create a `.env` file containing `GEMINI_API_KEY=your-key` (never commit it), then run:

```bash
streamlit run app.py
```

Without a key, choose **Saved sample output** on the Case Setup page. To run the tests:

```bash
python -m unittest discover -s tests -v
```
