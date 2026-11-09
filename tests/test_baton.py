"""Run with:  python -m unittest discover -s tests -v   (or: pytest)"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import extractor  # noqa: E402
import handover  # noqa: E402
import parsers  # noqa: E402
import permissions  # noqa: E402
import verifier  # noqa: E402

DEMO = Path(__file__).resolve().parent.parent / "demo_data"
DEMO_SOURCES = [
    ("meeting_notes.md", "Team"),
    ("club_chat.json", "Team"),
    ("tasks.csv", "Open"),
    ("finance_note.md", "Restricted"),
]


def load_demo_case():
    case_id = db.create_case("Campus Fest app handover", "Aarav", "Incoming Developer")
    for name, sensitivity in DEMO_SOURCES:
        text, chunks = parsers.parse_file(name, (DEMO / name).read_bytes())
        source_id = db.add_source(case_id, name, sensitivity, text)
        db.add_chunks(source_id, chunks)
    return case_id


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "test.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._old_path
        self._tmp.cleanup()


class ParserTests(unittest.TestCase):
    def test_csv_rows_become_chunks_with_unassigned_owner(self):
        text, chunks = parsers.parse_file("t.csv", b"task,owner\nA job,\nB job,Sam\n")
        self.assertEqual(chunks[0], "Task: A job | Owner: (not assigned)")
        self.assertEqual(chunks[1], "Task: B job | Owner: Sam")

    def test_chat_json_one_message_per_chunk(self):
        raw = b'{"messages":[{"time":"2026-10-01 10:00","author":"A","text":"hello there"}]}'
        _, chunks = parsers.parse_file("c.json", raw)
        self.assertEqual(chunks, ["[2026-10-01 10:00] A: hello there"])

    def test_empty_and_unknown_files_are_rejected(self):
        with self.assertRaises(ValueError):
            parsers.parse_file("x.md", b"   ")
        with self.assertRaises(ValueError):
            parsers.parse_file("x.pdf", b"data")

    def test_long_text_is_split(self):
        text = "\n\n".join(f"Paragraph number {i} " + "word " * 40 for i in range(10))
        _, chunks = parsers.parse_file("long.md", text.encode())
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= parsers.MAX_CHARS + 5 for c in chunks))


class VerifierTests(unittest.TestCase):
    def test_exact_quote_with_messy_whitespace_and_quotes(self):
        text = "Riya  will take\nthe login bug \u2019today\u2019"
        self.assertTrue(verifier.quote_in_text("Riya will take the login bug 'today'", text))

    def test_invented_or_too_short_quotes_fail(self):
        self.assertFalse(verifier.quote_in_text("we agreed to move hosting to AWS", "nothing here"))
        self.assertFalse(verifier.quote_in_text("Riya", "Riya will take the login bug"))

    def test_case_is_not_ignored(self):
        self.assertFalse(verifier.quote_in_text("riya will take the login bug", "Riya will take the login bug"))

    def test_locate_quote_corrects_a_wrong_chunk_and_wrong_source(self):
        chunks = {1: ["alpha text here", "the real quote lives here"], 2: ["another file entirely"]}
        self.assertEqual(verifier.locate_quote("the real quote lives here", chunks, 1, 0), (1, 1))
        self.assertEqual(verifier.locate_quote("another file entirely", chunks, 1, 0), (2, 0))
        self.assertIsNone(verifier.locate_quote("not present anywhere", chunks, 1, 0))

    def test_highlight_escapes_html(self):
        out = verifier.highlight("a <b>bold</b> claim is here", "a <b>bold</b> claim")
        self.assertNotIn("<b>", out)
        self.assertIn("baton-quote", out)

    def test_conflict_detection(self):
        def claim(i, t, subj, val, status="Verified"):
            return {"id": i, "claim_type": t, "subject": subj, "value": val, "status": status,
                    "source_id": 1, "chunk_index": 0, "sensitivity": "Team"}
        claims = [
            claim(1, "owner", "login bug owner", "Riya"),
            claim(2, "owner", "login bug owner", "Kabir"),
            claim(3, "open_task", "fix login bug", "Riya"),
            claim(4, "owner", "venue list owner", "Aarav"),
            claim(5, "owner", "venue list owner", "Aarav"),
        ]
        self.assertEqual(verifier.find_conflicts(claims), {1, 2, 3})

    def test_missing_checklist(self):
        def claim(i, t, subj, val):
            return {"id": i, "claim_type": t, "subject": subj, "value": val, "status": "Verified",
                    "source_id": 1, "chunk_index": 0, "sensitivity": "Open"}
        claims = [
            claim(1, "open_task", "renew hosting api key", ""),
            claim(2, "open_task", "fix login bug", ""),
            claim(3, "owner", "login bug owner", "Riya"),
            claim(4, "dependency", "payment sandbox approval", ""),
        ]
        missing = verifier.find_missing(claims)
        self.assertEqual(sorted(m["claim_type"] for m in missing), ["contact", "owner"])
        self.assertTrue(any("renew hosting api key" in m["statement"] for m in missing))


class PermissionTests(unittest.TestCase):
    def test_role_levels(self):
        self.assertTrue(permissions.can_see("Project Lead", "Restricted"))
        self.assertFalse(permissions.can_see("Incoming Developer", "Restricted"))
        self.assertFalse(permissions.can_see("Incoming Volunteer", "Team"))
        self.assertFalse(permissions.can_see("Stranger", "Open"))

    def test_strictest(self):
        self.assertEqual(permissions.strictest(["Open", "Restricted", "Team"]), "Restricted")
        self.assertEqual(permissions.strictest([]), "Restricted")


class EndToEndTests(DatabaseTestCase):
    def test_sample_extraction_and_no_leaks(self):
        case_id = load_demo_case()
        summary = extractor.run_extraction(case_id, use_cached=True)
        claims = db.list_claims(case_id)

        self.assertEqual(summary["Unverified"], 1)  # the deliberately invented AWS claim
        self.assertEqual(summary["Missing"], 3)
        self.assertEqual(summary["Conflicting"], 3)  # Riya vs Kabir on the login bug
        self.assertEqual(summary["Inferred"], 1)
        aws = [c for c in claims if "AWS" in c["statement"]][0]
        self.assertEqual(aws["status"], "Unverified")

        for c in claims:
            db.set_review_state(c["id"], "accepted")
        accepted = db.list_claims(case_id, "accepted")

        for role in ("Incoming Developer", "Incoming Volunteer"):
            visible, hidden = permissions.split_by_role(accepted, role)
            text = " ".join(c["statement"] + " " + c["quote"] for c in visible).lower()
            self.assertNotIn("printhub", text, role)
            self.assertNotIn("treasurer", text, role)
            self.assertGreater(hidden, 0)
        volunteer, _ = permissions.split_by_role(accepted, "Incoming Volunteer")
        self.assertTrue(all(c["sensitivity"] == "Open" for c in volunteer))

        plan = handover.build_plan(permissions.split_by_role(accepted, "Incoming Developer")[0])
        self.assertTrue(plan)
        self.assertNotIn("printhub", " ".join(s["text"] for s in plan).lower())

    def test_timeline_uses_chat_dates(self):
        case_id = load_demo_case()
        extractor.run_extraction(case_id, use_cached=True)
        events = handover.build_timeline(db.list_claims(case_id), db.get_chunk)
        self.assertTrue(events)
        self.assertEqual(events, sorted(events, key=lambda e: (e[0], e[1]["id"])))

    def test_edit_creates_a_new_version(self):
        case_id = load_demo_case()
        extractor.run_extraction(case_id, use_cached=True)
        claim = db.list_claims(case_id)[0]
        db.edit_claim(claim["id"], "Edited statement")
        versions = db.list_claim_versions(claim["id"])
        self.assertEqual([v["version"] for v in versions], [1, 2])
        self.assertEqual(db.get_claim(claim["id"])["statement"], "Edited statement")

    def test_extractor_input_checks(self):
        raw = [
            {"claim_type": "Open Task", "statement": "Do it", "quote": None, "chunk_index": "2"},
            {"claim_type": "nonsense", "statement": "bad type"},
            {"claim_type": "risk", "statement": ""},
            "not an object",
        ]
        good, skipped = extractor.validate_claims(raw)
        self.assertEqual(len(good), 1)
        self.assertEqual((good[0].claim_type, good[0].chunk_index, good[0].quote), ("open_task", 2, ""))
        self.assertEqual(skipped, 3)
        data = extractor.parse_llm_json('```json\n{"claims": [{"claim_type": "risk", "statement": "x"}]}\n```')
        self.assertEqual(len(data), 1)


if __name__ == "__main__":
    unittest.main()
