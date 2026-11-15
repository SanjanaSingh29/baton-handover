# Baton

**Turn scattered project activity into a handover people can trust.**

Baton is a Streamlit knowledge-handover application. It reads authorised project files, builds a ledger of decisions, owners, open work, risks and contacts, checks statements against source quotes, and leaves approval to a Project Lead.

**Live app:** https://baton-root-cause.streamlit.app/

## Roles and Access

Baton currently uses a **demo role selector** instead of account authentication.

- Users can select Project Lead, Incoming Developer or Incoming Volunteer.
- Project Lead can create cases, upload sources, run extraction, conduct interviews, review claims, approve handovers and inspect history.
- Incoming Developer can view Open and Team information.
- Incoming Volunteer can view Open information only.
- Role-based filtering and sensitive-information redaction are applied to the handover view.

**Important:** Role selection is for demonstration purposes only. It does not verify user identity or provide secure access control. Anyone accessing the application can switch roles. Do not use this mode for confidential or production data.

## Workflow

1. The Project Lead selects their role and creates a case.
2. The lead uploads authorised `.md`, `.txt`, `.csv` or chat `.json` sources and assigns sensitivity labels.
3. Gemini proposes claims with exact source quotes.
4. Python verifies whether the quotes exist, detects conflicts and identifies missing owners or contacts.
5. The person leaving can answer gap and conflict questions.
6. The Project Lead reviews, edits, accepts or rejects claims, then approves the handover.
7. Incoming users select their role and see the information permitted for that role.
8. Successors can acknowledge receipt. The Project Lead can inspect history and audit records.

## Roles

| Role | Information visible |
|---|---|
| Project Lead | Open, Team and Restricted |
| Incoming Developer | Open and Team |
| Incoming Volunteer | Open only |

A claim takes the sensitivity of the source where its quote was found. A claim with no known source is treated as Restricted.

## Technology

- Python and Streamlit
- SQLite
- Google Gemini through `google-genai`
- pandas and ReportLab
- unittest

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Create a `.env` file containing:

```env
GEMINI_API_KEY=your-key
```

Never commit `.env` or expose your API key.

Run automated tests:

```powershell
python -m unittest discover -s tests -v
```

## Security Limitations

- Demo role selection does not authenticate users or enforce secure identity-based permissions.
- This version uses a shared SQLite database and does not provide per-organisation or per-case membership isolation.
- Source sensitivity is manually assigned.
- Quote verification proves that a quote exists, not that the AI's interpretation is correct.
- Streamlit Community Cloud's local filesystem is not durable storage. SQLite data may be lost on restart or redeployment. Use managed persistent storage before relying on it.
- Do not upload confidential information unless the project owner has permission and the deployment's data-handling arrangements are appropriate.
