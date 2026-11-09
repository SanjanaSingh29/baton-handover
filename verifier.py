"""Plain-code checks that the AI cannot skip: quote matching, conflicts and missing items.

Nothing in this file calls an AI model.
"""
import html
import re
import unicodedata

MIN_QUOTE_CHARS = 12

_REPLACEMENTS = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ",
}

STOP_WORDS = {
    "owner", "owners", "task", "tasks", "the", "a", "an", "of", "for", "to", "fix", "fixing",
    "finish", "write", "renew", "test", "update", "complete", "who", "responsible", "ownership",
    "reason", "is", "and", "in", "on",
}

NO_VALUE = {
    "", "none", "unknown", "n/a", "na", "not assigned", "(not assigned)", "unassigned",
    "nobody", "no one", "tbd", "(blank)", "not stated", "not specified",
}

CONFLICT_FAMILY = {
    "owner": "ownership",
    "open_task": "ownership",
    "decision": "decision",
    "contact": "contact",
}


def normalize(text):
    """Collapse whitespace and unify quote and dash styles. Case is NOT ignored."""
    text = unicodedata.normalize("NFKC", text or "")
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def quote_in_text(quote, text):
    nq = normalize(quote)
    return len(nq) >= MIN_QUOTE_CHARS and nq in normalize(text)


def locate_quote(quote, chunks_by_source, prefer_source=None, prefer_chunk=None):
    """Find the exact quote. Returns (source_id, chunk_index) or None if it is nowhere.

    Order: the chunk the AI cited, the rest of that source, then every other source.
    """
    order = []
    if prefer_source in chunks_by_source:
        texts = chunks_by_source[prefer_source]
        if prefer_chunk is not None and 0 <= prefer_chunk < len(texts):
            order.append((prefer_source, prefer_chunk))
        order += [(prefer_source, i) for i in range(len(texts)) if i != prefer_chunk]
    for sid, texts in chunks_by_source.items():
        if sid != prefer_source:
            order += [(sid, i) for i in range(len(texts))]
    for sid, idx in order:
        if quote_in_text(quote, chunks_by_source[sid][idx]):
            return sid, idx
    return None


def highlight(chunk_text, quote):
    """Return safe HTML of the chunk with the quote highlighted."""
    chunk_text = chunk_text or ""
    q = (quote or "").strip()
    start = end = -1
    if q:
        i = chunk_text.find(q)
        if i >= 0:
            start, end = i, i + len(q)
        else:
            tokens = q.split()
            if tokens:
                m = re.search(r"\s+".join(re.escape(t) for t in tokens), chunk_text)
                if m:
                    start, end = m.span()
    if start < 0:
        body = html.escape(chunk_text)
    else:
        body = (
            html.escape(chunk_text[:start])
            + '<span class="baton-quote">' + html.escape(chunk_text[start:end]) + "</span>"
            + html.escape(chunk_text[end:])
        )
    return body.replace("\n", "<br>")


# ---------- conflicts and missing items ----------
def tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP_WORDS}


def same_subject(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    if inter == 0:
        return False
    return inter / len(ta | tb) >= 0.6 or (inter >= 2 and (ta <= tb or tb <= ta))


def has_value(value):
    return normalize(value).lower() not in NO_VALUE


def same_value(a, b):
    na, nb = normalize(a).lower(), normalize(b).lower()
    return na == nb or na in nb or nb in na


def find_conflicts(claims):
    """Return the ids of claims whose sources disagree about the same subject."""
    candidates = [
        c for c in claims
        if c["claim_type"] in CONFLICT_FAMILY
        and c["status"] in ("Verified", "Inferred")
        and tokens(c["subject"])
        and has_value(c["value"])
    ]
    groups = []
    for c in candidates:
        family = CONFLICT_FAMILY[c["claim_type"]]
        for g in groups:
            if g["family"] == family and same_subject(g["subject"], c["subject"]):
                g["claims"].append(c)
                break
        else:
            groups.append({"family": family, "subject": c["subject"], "claims": [c]})

    conflicting = set()
    for g in groups:
        distinct = []
        for c in g["claims"]:
            if not any(same_value(c["value"], d) for d in distinct):
                distinct.append(c["value"])
        if len(distinct) > 1:
            conflicting.update(c["id"] for c in g["claims"])
    return conflicting


def find_missing(claims):
    """Checklist: every open task needs an owner, every dependency needs a contact."""
    usable = ("Verified", "Inferred", "Conflicting")
    missing, seen = [], []
    for c in claims:
        if c["status"] not in usable or has_value(c["value"]):
            continue
        if c["claim_type"] == "open_task":
            answered = any(
                o["id"] != c["id"] and o["claim_type"] in ("owner", "open_task")
                and o["status"] in usable and has_value(o["value"])
                and same_subject(o["subject"], c["subject"])
                for o in claims
            )
            kind, label = "owner", "owner"
        elif c["claim_type"] == "dependency":
            answered = any(
                o["id"] != c["id"] and o["claim_type"] == "contact"
                and o["status"] in usable and has_value(o["value"])
                and same_subject(o["subject"], c["subject"])
                for o in claims
            )
            kind, label = "contact", "contact"
        else:
            continue
        if answered or any(same_subject(s, c["subject"]) and k == kind for s, k in seen):
            continue
        seen.append((c["subject"], kind))
        missing.append({
            "claim_type": kind,
            "statement": f'No {label} is recorded for "{c["subject"]}".',
            "subject": f'{c["subject"]} {label}',
            "source_id": c["source_id"],
            "chunk_index": c["chunk_index"],
            "sensitivity": c["sensitivity"],
        })
    return missing