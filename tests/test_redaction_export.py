"""Tests for redaction, the access audit and the PDF export. Run: python -m unittest discover -s tests -v"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import audit  # noqa: E402
import db  # noqa: E402
import export  # noqa: E402
import extractor  # noqa: E402
import handover  # noqa: E402
import interview  # noqa: E402
import parsers  # noqa: E402
import permissions  # noqa: E402
import redaction  # noqa: E402

DEMO = Path(__file__).resolve().parent.parent / "demo_data"
DEMO_SOURCES = [
    ("meeting_notes.md", "Team"),
    ("club_chat.json", "Team"),
    ("tasks.csv", "Open"),
    ("finance_note.md", "Restricted"),
]


class RedactionTests(unittest.TestCase):
    def test_masks_each_kind_of_detail(self):
        text = ("Mail it-office@college.example or call +91 98765 43210 / 98765 43210. "
                "Paid Rs 18,000 and INR 5000 and \u20b9 2,500. Card 4111111111111111. Key sk-abcdefghijklmnopqrstuv.")
        out, n = redaction.redact(text)
        for secret in ("it-office@college.example", "98765 43210", "18,000", "5000", "2,500",
                       "4111111111111111", "sk-abcdefghijklmnopqrstuv"):
            self.assertNotIn(secret, out)
        for mask in ("[email hidden]", "[phone hidden]", "[amount hidden]", "[number hidden]", "[secret hidden]"):
            self.assertIn(mask, out)
        self.assertGreaterEqual(n, 8)

    def test_ordinary_text_dates_and_times_are_not_touched(self):
        text = "[2026-10-15 09:50] Meera: Registration closes on 20 October, the hosting key expires on 25 October."
        out, n = redaction.redact(text)
        self.assertEqual((out, n), (text, 0))

    def test_redact_claim_masks_text_fields_and_counts(self):
        claim = {"id": 1, "statement": "Ask 98765 43210", "subject": "x", "value": "a@b.co", "quote": "Rs 500 now",
                 "status": "Verified"}
        masked, n = redaction.redact_claim(claim)
        self.assertEqual(n, 3)
        self.assertEqual(masked["status"], "Verified")
        self.assertIn("[phone hidden]", masked["statement"])
        self.assertEqual(claim["statement"], "Ask 98765 43210")  # the original is not changed

    def test_which_roles_get_redaction(self):
        self.assertFalse(redaction.applies_to("Project Lead"))
        self.assertTrue(redaction.applies_to("Incoming Developer"))
        self.assertTrue(redaction.applies_to("Incoming Volunteer"))
        self.assertTrue(redaction.applies_to("Stranger"))


class AuditAndExportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "t.db"
        db.init_db()
        self.case_id = db.create_case("Campus Fest app handover", "Aarav", "Incoming Developer")
        for name, level in DEMO_SOURCES:
            text, chunks = parsers.parse_file(name, (DEMO / name).read_bytes())
            sid = db.add_source(self.case_id, name, level, text)
            db.add_chunks(sid, chunks)
        extractor.run_extraction(self.case_id, use_cached=True)
        q = next(x for x in interview.build_questions(db.list_claims(self.case_id))
                 if x["kind"] == "missing_owner" and "renew hosting api key" in x["text"])
        interview.save_answer(self.case_id, q, choice="the treasurer", sensitivity="Restricted", leaver="Aarav")
        for c in db.list_claims(self.case_id):
            db.set_review_state(c["id"], "accepted")
        self.case = db.get_case(self.case_id)
        self.sources = {s["id"]: s for s in db.list_sources(self.case_id)}

    def tearDown(self):
        db.DB_PATH = self._old
        self._tmp.cleanup()

    def view_for(self, role):
        accepted = [c for c in db.list_claims(self.case_id, "accepted") if c["status"] != "Unverified"]
        visible, hidden = permissions.split_by_role(accepted, role)
        count = 0
        if redaction.applies_to(role):
            masked = []
            for c in visible:
                m, n = redaction.redact_claim(c)
                masked.append(m)
                count += n
            visible = masked
        plan = handover.build_plan(visible)
        return visible, plan, hidden, count

    def model_for(self, role):
        visible, plan, hidden, count = self.view_for(role)
        return export.document_model(self.case, role, visible, plan, hidden, count, self.sources,
                                     db.get_chunk, interview.answer_for_claim)

    def test_no_restricted_or_unmasked_detail_in_any_lower_role_export(self):
        for role in ("Incoming Developer", "Incoming Volunteer"):
            text = export.model_text(self.model_for(role)).lower()
            for forbidden in ("printhub", "treasurer", "18,000", "it-office@college.example", "98765 43210"):
                self.assertNotIn(forbidden, text, f"{role} export leaked {forbidden}")
            visible, plan, hidden, count = self.view_for(role)
            pdf = export.build_pdf(self.case, role, visible, plan, hidden, count, self.sources,
                                   db.get_chunk, interview.answer_for_claim)
            self.assertTrue(pdf.startswith(b"%PDF"))
            for forbidden in (b"PrintHub", b"treasurer", b"18,000", b"it-office@college.example"):
                self.assertNotIn(forbidden, pdf, f"{role} PDF leaked {forbidden!r}")

    def test_developer_sees_masked_contact_details(self):
        model = self.model_for("Incoming Developer")
        text = export.model_text(model)
        self.assertIn("[email hidden]", text)
        self.assertIn("[phone hidden]", text)
        self.assertGreater(model["redactions"], 0)

    def test_lead_export_has_everything_unmasked(self):
        model = self.model_for("Project Lead")
        text = export.model_text(model).lower()
        self.assertIn("printhub", text)
        self.assertIn("it-office@college.example", text)
        self.assertEqual(model["redactions"], 0)
        self.assertEqual(model["hidden"], 0)

    def test_hidden_counts_and_unverified_are_never_exported(self):
        dev = self.model_for("Incoming Developer")
        vol = self.model_for("Incoming Volunteer")
        self.assertGreater(vol["hidden"], dev["hidden"])
        self.assertNotIn("aws", export.model_text(self.model_for("Project Lead")).lower())

    def test_export_includes_plan_evidence_and_stated_answers(self):
        model = self.model_for("Project Lead")
        self.assertTrue(model["plan"])
        self.assertTrue(any(e["status"] == "Stated" and "Stated by" in e["where"] for e in model["evidence"]))
        self.assertTrue(any(e["status"] == "Verified" and "chunk" in e["where"] for e in model["evidence"]))

    def test_file_name_is_safe(self):
        self.assertEqual(export.file_name({"title": "Campus Fest app handover"}, "Incoming Developer"),
                         "baton-campus-fest-app-handover-incoming-developer.pdf")
        self.assertEqual(export.file_name({"title": "../../x y"}, "Lead!"), "baton-x-y-lead.pdf")

    def test_access_audit_records_and_summarises(self):
        audit.log_access(self.case_id, "Incoming Developer", "view", 14, 2, 3)
        audit.log_access(self.case_id, "Incoming Volunteer", "view", 6, 12, 0)
        audit.log_access(self.case_id, "Incoming Developer", "export", 14, 2, 3)
        rows = audit.list_access(self.case_id)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["action"], "export")  # newest first
        self.assertEqual(audit.summarize(rows), {"views": 2, "exports": 1, "hidden": 16, "redactions": 6})


if __name__ == "__main__":
    unittest.main()
