"""Turn uploaded files into plain text plus numbered chunks.

Every claim Baton makes points at one chunk, so the chunk is the unit of evidence.
"""
import csv
import io
import json
import re

MAX_CHARS = 700
ASSIGNEE_HEADERS = {"owner", "assignee", "assigned to", "assigned_to"}


def decode(raw):
    if isinstance(raw, str):
        text = raw
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_long(text, max_chars):
    """Split one very long paragraph on line breaks, then on sentences, then hard."""
    pieces = []
    for line in text.split("\n"):
        if len(line) <= max_chars:
            pieces.append(line)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", line)
        buf = ""
        for s in sentences:
            while len(s) > max_chars:
                if buf:
                    pieces.append(buf)
                    buf = ""
                pieces.append(s[:max_chars])
                s = s[max_chars:]
            if buf and len(buf) + 1 + len(s) > max_chars:
                pieces.append(buf)
                buf = s
            else:
                buf = f"{buf} {s}".strip()
        if buf:
            pieces.append(buf)
    return pieces


def chunk_paragraphs(text, max_chars=MAX_CHARS):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paragraphs:
        parts = [p] if len(p) <= max_chars else _split_long(p, max_chars)
        for part in parts:
            if buf and len(buf) + 2 + len(part) > max_chars:
                chunks.append(buf)
                buf = part
            else:
                buf = f"{buf}\n\n{part}" if buf else part
    if buf:
        chunks.append(buf)
    return chunks


def parse_csv(text):
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if len(rows) < 2:
        raise ValueError("The CSV needs a header row and at least one data row.")
    headers = [h.strip() for h in rows[0]]
    lines = []
    for row in rows[1:]:
        parts = []
        for i, header in enumerate(headers):
            value = row[i].strip() if i < len(row) else ""
            if not value:
                value = "(not assigned)" if header.lower() in ASSIGNEE_HEADERS else "(blank)"
            parts.append(f"{header.title()}: {value}")
        lines.append(" | ".join(parts))
    return lines


def parse_chat_json(text):
    data = json.loads(text)
    messages = data.get("messages") if isinstance(data, dict) else data
    if not isinstance(messages, list) or not messages or not all(isinstance(m, dict) for m in messages):
        return None
    lines = []
    for m in messages:
        when = m.get("time") or m.get("timestamp") or m.get("date") or ""
        who = m.get("author") or m.get("user") or m.get("sender") or m.get("from") or "Unknown"
        body = m.get("text") or m.get("message") or m.get("content") or ""
        if not str(body).strip():
            continue
        stamp = f"[{when}] " if when else ""
        lines.append(f"{stamp}{who}: {str(body).strip()}")
    return lines or None


def parse_file(name, raw):
    """Return (text, chunks) for an uploaded file. Raises ValueError with a friendly message."""
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    text = decode(raw)
    if not text.strip():
        raise ValueError(f"{name} is empty.")

    if ext in ("md", "txt"):
        return text, chunk_paragraphs(text)

    if ext == "csv":
        lines = parse_csv(text)
        return "\n".join(lines), lines

    if ext == "json":
        try:
            lines = parse_chat_json(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} is not valid JSON: {exc}") from exc
        if lines:
            return "\n".join(lines), lines
        pretty = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        return pretty, chunk_paragraphs(pretty)

    raise ValueError(f"{name}: unsupported file type. Use .md, .txt, .csv or .json.")