
"""Access audit helpers for Baton."""

import db


def log_access(case_id, role, action, items_shown, items_hidden, redactions):
    """Record a handover view or PDF export."""
    detail = (
        f"Role: {role}; "
        f"Shown: {items_shown}; "
        f"Hidden: {items_hidden}; "
        f"Redactions: {redactions}"
    )
    db.log_action(case_id, action, detail)


def list_access(case_id):
    """Retrieve access records for a case."""
    records = db.list_audit(case_id)
    rows = []

    for record in records:
        if record["action"] not in ("view", "export"):
            continue

        detail = record.get("detail") or ""

        values = {}
        for part in detail.split("; "):
            if ": " in part:
                key, value = part.split(": ", 1)
                values[key] = value

        rows.append({
            "created_at": record["created_at"],
            "role": values.get("Role", "Unknown"),
            "action": record["action"],
            "items_shown": int(values.get("Shown", 0)),
            "items_hidden": int(values.get("Hidden", 0)),
            "redactions": int(values.get("Redactions", 0)),
        })

    return rows


def summarize(rows):
    """Calculate totals for the access audit dashboard."""
    return {
        "views": sum(1 for row in rows if row["action"] == "view"),
        "exports": sum(1 for row in rows if row["action"] == "export"),
        "hidden": sum(row["items_hidden"] for row in rows),
        "redactions": sum(row["redactions"] for row in rows),
    }
