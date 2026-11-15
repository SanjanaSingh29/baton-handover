"""Evidence-driven gap interview.

Every Missing, Conflicting or Unverified item becomes a short question for the person leaving.
The answers are saved as claims with the status "Stated": evidence that comes from a person,
clearly separate from claims verified against a project file.

Questions come from fixed templates, so this feature needs no AI and uses no API quota.
"""
import re

import db
import verifier
from config import SENSITIVITIES

OTHER_LABEL = "Something else"


def ensure_tables():
    with db.get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                question_key TEXT NOT NULL,
                question TEXT NOT NULL,
                choice TEXT NOT NULL,
                note TEXT,
                answer TEXT NOT NULL,
                answered_by TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                stated_claim_id INTEGER,
                created_at TEXT NOT NULL
            )
            """
        )


def _key(text):
    tokens = sorted(verifier.tokens(text))
    return " ".join(tokens) if tokens else re.sub(r"\W+", "-", (text or "").lower())[:40]


def base_subject(subject):
    """'renew hosting api key owner' -> 'renew hosting api key'."""
    parts = (subject or "").rsplit(" ", 1)
    if len(parts) == 2 and parts[1] in ("owner", "contact"):
        return parts[0]
    return subject or ""


def stated_sentence(leaver, claim_type, base, value):
    if claim_type == "owner":
        return f'{leaver} confirms that the owner of "{base}" is {value}.'
    if claim_type == "contact":
        return f'{leaver} confirms that the contact for "{base}" is {value}.'
    return f'{leaver} confirms that "{base}" is {value}.'


def build_questions(claims):
    """Turn conflicts, gaps and unsupported claims into questions. Each has a stable key."""
    questions = []

    groups = []
    for c in claims:
        if c["status"] != "Conflicting":
            continue
        for g in groups:
            if verifier.same_subject(g[0]["subject"], c["subject"]):
                g.append(c)
                break
        else:
            groups.append([c])
    for g in groups:
        values = []
        for c in g:
            if verifier.has_value(c["value"]) and not any(verifier.same_value(c["value"], v) for v in values):
                values.append(c["value"])
        types = {c["claim_type"] for c in g}
        claim_type = "owner" if types & {"owner", "open_task"} else g[0]["claim_type"]
        owner_like = [c for c in g if c["claim_type"] == "owner"]
        subject = (owner_like or g)[0]["subject"]
        base = base_subject(subject)
        questions.append({
            "kind": "conflict", "key": "conflict:" + _key(base), "claim_type": claim_type,
            "subject": subject, "base": base, "options": values, "claim_ids": [c["id"] for c in g],
            "text": f'Your files disagree about "{base}": {" or ".join(values)}. Which one is correct?',
        })

    for c in claims:
        if c["status"] != "Missing":
            continue
        base = base_subject(c["subject"])
        if c["claim_type"] == "owner":
            kind, text = "missing_owner", f'Who owns "{base}"?'
        else:
            kind, text = "missing_contact", f'Who should the successor ask about "{base}"?'
        questions.append({
            "kind": kind, "key": f"{kind}:" + _key(base), "claim_type": c["claim_type"],
            "subject": c["subject"], "base": base, "options": [], "claim_ids": [c["id"]], "text": text,
        })

    for c in claims:
        if c["status"] != "Unverified":
            continue
        label = c["subject"] or c["statement"][:40]
        questions.append({
            "kind": "unverified", "key": "unverified:" + _key(label), "claim_type": c["claim_type"],
            "subject": c["subject"], "base": base_subject(c["subject"]), "options": ["Yes", "No", "Not sure"],
            "claim_ids": [c["id"]], "statement": c["statement"], "value": c["value"],
            "text": f'No project file supports this statement: "{c["statement"]}" Is it true?',
        })

    seen = {}
    for q in questions:
        n = seen.get(q["key"], 0)
        seen[q["key"]] = n + 1
        if n:
            q["key"] = f'{q["key"]}#{n}'
    return questions


def list_answers(case_id):
    """Saved answers for a case, as a dict keyed by question key."""
    ensure_tables()
    with db.get_conn() as conn:
        rows = db._all(conn, "SELECT * FROM interview_answers WHERE case_id = ? ORDER BY id", (case_id,))
    return {r["question_key"]: r for r in rows}


def answer_for_claim(claim_id):
    ensure_tables()
    with db.get_conn() as conn:
        return db._one(conn, "SELECT * FROM interview_answers WHERE stated_claim_id = ?", (claim_id,))


def is_answered(answer, existing_claim_ids):
    """An answer counts only while the claim it created still exists (a rebuild removes claims)."""
    if not answer:
        return False
    return answer["stated_claim_id"] is None or answer["stated_claim_id"] in existing_claim_ids


def save_answer(case_id, question, choice="", other="", note="", answered_by="",
                sensitivity="Team", leaver="The person leaving"):
    """Save one answer. Creates a 'Stated' claim unless the answer is No or Not sure."""
    ensure_tables()
    kind = question["kind"]
    choice, other, note = (choice or "").strip(), (other or "").strip(), (note or "").strip()
    answered_by = (answered_by or "").strip() or leaver
    if sensitivity not in SENSITIVITIES:
        raise ValueError("Choose who may see this answer.")

    claim = None  # (claim_type, statement, subject, value)
    if kind == "conflict":
        value = other if choice == OTHER_LABEL else choice
        if not value:
            raise ValueError("Please choose an option, or type the correct answer.")
        core = value
        claim = (question["claim_type"], stated_sentence(leaver, question["claim_type"], question["base"], value),
                 question["subject"], value)
    elif kind in ("missing_owner", "missing_contact"):
        if not choice:
            raise ValueError("Please enter a name.")
        core = choice
        claim_type = "owner" if kind == "missing_owner" else "contact"
        claim = (claim_type, stated_sentence(leaver, claim_type, question["base"], choice),
                 f'{question["base"]} {claim_type}', choice)
    elif kind == "unverified":
        if choice not in ("Yes", "No", "Not sure"):
            raise ValueError("Please choose Yes, No or Not sure.")
        core = choice
        if choice == "Yes":
            claim = (question["claim_type"], f'{leaver} confirms: {question["statement"]}',
                     question["subject"], question.get("value", ""))
    else:
        raise ValueError(f"Unknown question type {kind!r}.")

    answer_text = core if not note else f"{core}. {note}"

    with db.get_conn() as conn:
        old = db._one(conn, "SELECT * FROM interview_answers WHERE case_id = ? AND question_key = ?",
                      (case_id, question["key"]))
    if old and old["stated_claim_id"]:
        with db.get_conn() as conn:
            conn.execute("DELETE FROM claims WHERE id = ?", (old["stated_claim_id"],))

    claim_id = None
    if claim:
        claim_type, statement, subject, value = claim
        claim_id = db.add_claim(case_id, claim_type, statement, subject, value, None, None,
                                answer_text, False, "Stated", sensitivity)

    with db.get_conn() as conn:
        conn.execute("DELETE FROM interview_answers WHERE case_id = ? AND question_key = ?",
                     (case_id, question["key"]))
        conn.execute(
            "INSERT INTO interview_answers (case_id, question_key, question, choice, note, answer, "
            "answered_by, sensitivity, stated_claim_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, question["key"], question["text"], core, note, answer_text, answered_by,
             sensitivity, claim_id, db._now()),
        )
    db.log_action(case_id, "interview_answer", f'{question["key"]}: {core}')
    return {"claim_id": claim_id, "answer": answer_text}