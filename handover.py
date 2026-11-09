"""Builds the first-week plan and the timeline from claims. No AI involved."""
import re

from verifier import has_value, same_subject

STAMP = re.compile(r"^\[(\d{4}-\d{2}-\d{2})(?: \d{2}:\d{2})?\]")


def build_timeline(claims, get_chunk):
    """Dated events: claims whose evidence chunk starts with a [YYYY-MM-DD] stamp."""
    events = []
    for c in claims:
        if c["status"] in ("Missing", "Unverified"):
            continue  # gaps and unsupported claims are not dated events
        if c.get("source_id") is None or c.get("chunk_index") is None:
            continue
        chunk = get_chunk(c["source_id"], c["chunk_index"])
        if not chunk:
            continue
        m = STAMP.match(chunk["text"])
        if m:
            events.append((m.group(1), c))
    events.sort(key=lambda e: (e[0], e[1]["id"]))
    return events


def build_plan(claims, limit=8):
    """An ordered list of first-week steps: settle conflicts, fill gaps, continue work, watch risks."""
    steps = []

    groups = []
    for c in claims:
        if c["status"] != "Conflicting":
            continue
        for g in groups:
            if same_subject(g[0]["subject"], c["subject"]):
                g.append(c)
                break
        else:
            groups.append([c])
    for g in groups:
        values = []
        for c in g:
            if has_value(c["value"]) and c["value"] not in values:
                values.append(c["value"])
        steps.append({
            "text": f'Settle the conflicting information about "{g[0]["subject"]}": ' + " or ".join(values),
            "status": "Conflicting",
        })

    for c in claims:
        if c["status"] == "Missing":
            steps.append({"text": f'Find out: {c["statement"]}', "status": "Missing"})

    for c in claims:
        if c["claim_type"] == "open_task" and c["status"] in ("Verified", "Inferred") and has_value(c["value"]):
            steps.append({"text": f'Continue "{c["subject"]}" (owner: {c["value"]})', "status": c["status"]})

    for c in claims:
        if c["claim_type"] == "risk" and c["status"] in ("Verified", "Inferred"):
            steps.append({"text": f'Watch out: {c["statement"]}', "status": c["status"]})

    return steps[:limit]