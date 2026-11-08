"""SQLite storage for Baton. Every table and helper the app needs lives here."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    leaver TEXT NOT NULL,
    successor_role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    sensitivity TEXT NOT NULL DEFAULT 'Team',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    claim_type TEXT NOT NULL,
    statement TEXT NOT NULL,
    subject TEXT,
    value TEXT,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    chunk_index INTEGER,
    quote TEXT,
    inferred INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Unverified',
    sensitivity TEXT NOT NULL DEFAULT 'Team',
    review_state TEXT NOT NULL DEFAULT 'pending',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    statement TEXT NOT NULL,
    edited_by TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS acknowledgements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    acknowledged_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
"""


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def _all(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


# ---------- cases ----------
def create_case(title, leaver, successor_role):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cases (title, leaver, successor_role, created_at) VALUES (?, ?, ?, ?)",
            (title, leaver, successor_role, _now()),
        )
        return cur.lastrowid


def list_cases():
    with get_conn() as conn:
        return _all(conn, "SELECT * FROM cases ORDER BY id DESC")


def get_case(case_id):
    with get_conn() as conn:
        return _one(conn, "SELECT * FROM cases WHERE id = ?", (case_id,))


def set_case_status(case_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE cases SET status = ? WHERE id = ?", (status, case_id))


# ---------- sources and chunks ----------
def add_source(case_id, filename, sensitivity, content):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sources (case_id, filename, sensitivity, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (case_id, filename, sensitivity, content, _now()),
        )
        return cur.lastrowid


def list_sources(case_id):
    with get_conn() as conn:
        return _all(conn, "SELECT * FROM sources WHERE case_id = ? ORDER BY id", (case_id,))


def get_source(source_id):
    with get_conn() as conn:
        return _one(conn, "SELECT * FROM sources WHERE id = ?", (source_id,))


def add_chunks(source_id, texts):
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO chunks (source_id, chunk_index, text) VALUES (?, ?, ?)",
            [(source_id, i, t) for i, t in enumerate(texts)],
        )


def list_chunks(source_id):
    with get_conn() as conn:
        return _all(
            conn, "SELECT * FROM chunks WHERE source_id = ? ORDER BY chunk_index", (source_id,)
        )


def get_chunk(source_id, chunk_index):
    with get_conn() as conn:
        return _one(
            conn,
            "SELECT * FROM chunks WHERE source_id = ? AND chunk_index = ?",
            (source_id, chunk_index),
        )


# ---------- claims ----------
def add_claim(case_id, claim_type, statement, subject=None, value=None, source_id=None,
              chunk_index=None, quote=None, inferred=False, status="Unverified",
              sensitivity="Team"):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO claims (case_id, claim_type, statement, subject, value, source_id, "
            "chunk_index, quote, inferred, status, sensitivity, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, claim_type, statement, subject, value, source_id, chunk_index, quote,
             int(inferred), status, sensitivity, _now()),
        )
        claim_id = cur.lastrowid
        conn.execute(
            "INSERT INTO claim_versions (claim_id, version, statement, edited_by, note, created_at) "
            "VALUES (?, 1, ?, 'Baton', 'Generated by Baton', ?)",
            (claim_id, statement, _now()),
        )
        return claim_id


def list_claims(case_id, review_state=None):
    sql = "SELECT * FROM claims WHERE case_id = ?"
    params = [case_id]
    if review_state:
        sql += " AND review_state = ?"
        params.append(review_state)
    sql += " ORDER BY id"
    with get_conn() as conn:
        return _all(conn, sql, params)


def get_claim(claim_id):
    with get_conn() as conn:
        return _one(conn, "SELECT * FROM claims WHERE id = ?", (claim_id,))


def update_claim_status(claim_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE claims SET status = ? WHERE id = ?", (status, claim_id))


def set_review_state(claim_id, state):
    with get_conn() as conn:
        conn.execute("UPDATE claims SET review_state = ? WHERE id = ?", (state, claim_id))


def edit_claim(claim_id, new_statement, editor="Project Lead", note="Edited by the lead"):
    """Save an edit as a new version so nothing is ever overwritten silently."""
    with get_conn() as conn:
        row = _one(conn, "SELECT version FROM claims WHERE id = ?", (claim_id,))
        new_version = row["version"] + 1
        conn.execute(
            "UPDATE claims SET statement = ?, version = ? WHERE id = ?",
            (new_statement, new_version, claim_id),
        )
        conn.execute(
            "INSERT INTO claim_versions (claim_id, version, statement, edited_by, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (claim_id, new_version, new_statement, editor, note, _now()),
        )


def list_claim_versions(claim_id):
    with get_conn() as conn:
        return _all(
            conn, "SELECT * FROM claim_versions WHERE claim_id = ? ORDER BY version", (claim_id,)
        )


def clear_claims(case_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM claims WHERE case_id = ?", (case_id,))


# ---------- acknowledgements and audit ----------
def add_acknowledgement(case_id, role, name):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO acknowledgements (case_id, role, name, acknowledged_at) VALUES (?, ?, ?, ?)",
            (case_id, role, name, _now()),
        )


def list_acknowledgements(case_id):
    with get_conn() as conn:
        return _all(
            conn, "SELECT * FROM acknowledgements WHERE case_id = ? ORDER BY id DESC", (case_id,)
        )


def log_action(case_id, action, detail=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (case_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
            (case_id, action, detail, _now()),
        )


def list_audit(case_id):
    with get_conn() as conn:
        return _all(conn, "SELECT * FROM audit_log WHERE case_id = ? ORDER BY id DESC", (case_id,))


def counts():
    with get_conn() as conn:
        return {
            "cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
            "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "claims": conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
        }