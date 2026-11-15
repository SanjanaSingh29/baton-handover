"""Tests for the gap interview. Run with:  python -m unittest discover -s tests -v"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import extractor  # noqa: E402
import handover  # noqa: E402
import interview  # noqa: E402
import parsers  # noqa: E402
import permissions  # noqa: E402

DEMO = Path(__file__).resolve().parent.parent / "demo_data"
DEMO_SOURCES = [
    ("meeting_notes.md", "Team"),
    ("club_chat.json", "Team"),
    ("tasks.csv", "Open"),
    ("finance_note.md", "Restricted"),
]


class InterviewTests(unittest.TestCase):
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

    def tearDown(self):
        db.DB_PATH = self._old
        self._tmp.cleanup()

    def questions(self):
        return interview.build_questions(db.list_claims(self.case_id))

    def find(self, kind, text):
        return next(q for q in self.questions() if q["kind"] == kind and text in q["text"])

    def test_questions_come_from_gaps_conflicts_and_unsupported_claims(self):
        kinds = sorted(q["kind"] for q in self.questions())
        self.assertEqual(kinds, ["conflict", "missing_contact", "missing_owner", "missing_owner", "unverified"])
        conflict = self.find("conflict", "login bug")
        self.assertEqual(sorted(conflict["options"]), ["Kabir", "Riya"])
        keys = [q["key"] for q in self.questions()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_missing_owner_answer_becomes_stated_claim_not_verified(self):
        q = self.find("missing_owner", "renew hosting api key")
        interview.save_answer(self.case_id, q, choice="Meera", note="She has the card", answered_by="Aarav",
                              sensitivity="Team", leaver="Aarav")
        stated = [c for c in db.list_claims(self.case_id) if c["status"] == "Stated"]
        self.assertEqual(len(stated), 1)
        self.assertEqual(stated[0]["value"], "Meera")
        self.assertEqual(stated[0]["claim_type"], "owner")
        self.assertIsNone(stated[0]["source_id"])
        self.assertEqual(stated[0]["review_state"], "pending")  # the lead still has to approve
        self.assertIn("She has the card", stated[0]["quote"])
        self.assertEqual(interview.answer_for_claim(stated[0]["id"])["answered_by"], "Aarav")

    def test_answered_gap_disappears_and_task_gets_its_owner(self):
        q = self.find("missing_owner", "renew hosting api key")
        interview.save_answer(self.case_id, q, choice="Meera", leaver="Aarav")
        claims = db.list_claims(self.case_id)
        gap_subjects = [c["subject"] for c in handover.unresolved_gaps(claims)]
        self.assertNotIn("renew hosting api key owner", gap_subjects)
        self.assertEqual(len(gap_subjects), 2)
        task = next(c for c in claims if c["subject"] == "renew hosting api key" and c["claim_type"] == "open_task")
        self.assertEqual(handover.owner_for(task, claims), ("Meera", True))

    def test_conflict_answer_shows_in_plan(self):
        q = self.find("conflict", "login bug")
        interview.save_answer(self.case_id, q, choice="Kabir", leaver="Aarav")
        plan = handover.build_plan(db.list_claims(self.case_id), limit=20)
        stated_steps = [s for s in plan if s["status"] == "Stated"]
        self.assertTrue(any("Kabir" in s["text"] and "login bug" in s["text"] for s in stated_steps))
        self.assertFalse(any(s["status"] == "Conflicting" for s in plan))

    def test_something_else_needs_text(self):
        q = self.find("conflict", "login bug")
        with self.assertRaises(ValueError):
            interview.save_answer(self.case_id, q, choice=interview.OTHER_LABEL, other="")
        interview.save_answer(self.case_id, q, choice=interview.OTHER_LABEL, other="Meera", leaver="Aarav")
        stated = [c for c in db.list_claims(self.case_id) if c["status"] == "Stated"]
        self.assertEqual(stated[0]["value"], "Meera")

    def test_unverified_yes_creates_claim_but_no_does_not(self):
        q = self.find("unverified", "AWS")
        interview.save_answer(self.case_id, q, choice="No", leaver="Aarav")
        self.assertEqual([c for c in db.list_claims(self.case_id) if c["status"] == "Stated"], [])
        interview.save_answer(self.case_id, q, choice="Yes", leaver="Aarav")
        stated = [c for c in db.list_claims(self.case_id) if c["status"] == "Stated"]
        self.assertEqual(len(stated), 1)
        self.assertIn("AWS", stated[0]["statement"])

    def test_reanswering_replaces_instead_of_duplicating(self):
        q = self.find("missing_owner", "test payment flow")
        interview.save_answer(self.case_id, q, choice="Riya", leaver="Aarav")
        interview.save_answer(self.case_id, q, choice="Kabir", leaver="Aarav")
        stated = [c for c in db.list_claims(self.case_id) if c["status"] == "Stated"]
        self.assertEqual([c["value"] for c in stated], ["Kabir"])
        self.assertEqual(len(interview.list_answers(self.case_id)), 1)

    def test_validation(self):
        q = self.find("missing_owner", "renew hosting api key")
        with self.assertRaises(ValueError):
            interview.save_answer(self.case_id, q, choice="  ")
        with self.assertRaises(ValueError):
            interview.save_answer(self.case_id, q, choice="Meera", sensitivity="Secret")

    def test_stated_answer_respects_the_sensitivity_chosen(self):
        q = self.find("missing_owner", "renew hosting api key")
        interview.save_answer(self.case_id, q, choice="the treasurer", sensitivity="Restricted", leaver="Aarav")
        for c in db.list_claims(self.case_id):
            db.set_review_state(c["id"], "accepted")
        accepted = db.list_claims(self.case_id, "accepted")
        for role in ("Incoming Developer", "Incoming Volunteer"):
            visible, _ = permissions.split_by_role(accepted, role)
            self.assertFalse(any(c["status"] == "Stated" for c in visible), role)
            plan = " ".join(s["text"] for s in handover.build_plan(visible, limit=20)).lower()
            self.assertNotIn("treasurer", plan, role)
        lead, _ = permissions.split_by_role(accepted, "Project Lead")
        self.assertTrue(any(c["status"] == "Stated" for c in lead))

    def test_answers_survive_a_rebuild_as_prefilled_but_open(self):
        q = self.find("missing_owner", "renew hosting api key")
        interview.save_answer(self.case_id, q, choice="Meera", leaver="Aarav")
        extractor.run_extraction(self.case_id, use_cached=True)  # a rebuild removes every claim
        claims = db.list_claims(self.case_id)
        answers = interview.list_answers(self.case_id)
        fresh = next(x for x in interview.build_questions(claims) if x["key"] == q["key"])
        old = answers[fresh["key"]]
        self.assertFalse(interview.is_answered(old, {c["id"] for c in claims}))
        self.assertEqual(old["choice"], "Meera")  # still there to prefill the form

    def test_statuses_for_ledger(self):
        from config import STATUSES
        self.assertIn("Stated", STATUSES)


if __name__ == "__main__":
    unittest.main()