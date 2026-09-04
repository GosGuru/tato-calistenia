"""Synthetic regression tests; never open the private CRM."""
import tempfile
import unittest
from pathlib import Path
import crm_tracker as crm


def event(**changes):
    value = dict(lead_key="synthetic", event_type="outbound_sent",
                 occurred_at="2026-09-03T10:00:00-03:00", actor="maximo",
                 evidence_state="observed", message_text="synthetic bubble")
    value.update(changes)
    return value


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = crm.connect(Path(self.tmp.name) / "test.sqlite3")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def report(self):
        return crm.eod_report(self.db, "2026-09-03")

    def test_evidence_upgrade_is_one_bubble(self):
        crm.record_events(self.db, [event(), event(evidence_state="verified"), event()])
        self.assertEqual(self.report()["metrics"]["outbound_bubbles"], 1)
        self.assertEqual(crm.get_lead(self.db, "synthetic")["recent_events"][0]["evidence_state"], "verified")

    def test_equivalent_offsets_and_local_day(self):
        crm.record_events(self.db, [event(occurred_at="2026-09-04T01:00:00Z"),
                                    event(occurred_at="2026-09-03T22:00:00-03:00")])
        self.assertEqual(self.report()["metrics"]["outbound_bubbles"], 1)

    def test_old_duplicate_cannot_regress_state(self):
        old = event(phase="contexto", quality="baja")
        crm.record_events(self.db, [old, event(occurred_at="2026-09-04T10:00:00-03:00", phase="conversion", quality="alta")])
        crm.record_events(self.db, [old])
        self.assertEqual(crm.get_lead(self.db, "synthetic")["lead"]["phase"], "conversion")
        self.assertEqual(self.report()["quality"]["baja"], 1)

    def test_drafts_do_not_affect_quality(self):
        crm.record_events(self.db, [event(event_type="dm_drafted", evidence_state="draft", quality="alta")])
        self.assertEqual(sum(self.report()["quality"].values()), 0)

    def test_reply_before_todays_outbound_is_late(self):
        crm.record_events(self.db, [event(occurred_at="2026-09-02T12:00:00-03:00"),
            event(event_type="inbound_received", actor="lead", occurred_at="2026-09-03T09:00:00-03:00"), event()])
        self.assertEqual(self.report()["metrics"]["late_responses"], 1)
        self.assertEqual(self.report()["metrics"]["responded_same_day_cohort"], 0)

    def test_ambiguous_timestamp_rejected(self):
        for value in ("2026-09-03", "2026-09-03T12:00:00"):
            with self.assertRaises(ValueError):
                crm.validate_event(event(occurred_at=value))

    def test_invalid_batch_is_atomic(self):
        with self.assertRaises(ValueError):
            crm.record_events(self.db, [event(), event(actor="invalid")])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_coverage_is_honest(self):
        self.assertEqual(self.report()["coverage"]["status"], "partial")

    def test_out_of_order_ingestion(self):
        crm.record_events(self.db, [event(phase="conversion"), event(occurred_at="2026-09-02T10:00:00-03:00", phase="contexto")])
        self.assertEqual(crm.get_lead(self.db, "synthetic")["lead"]["phase"], "conversion")

    def test_followup_reobservation_is_same_bubble(self):
        crm.record_events(self.db, [event(), event(event_type="followup_sent", actor="agent", evidence_state="verified")])
        self.assertEqual(self.report()["metrics"]["outbound_bubbles"], 1)
        self.assertEqual(self.report()["metrics"]["followups_unique_contacts"], 1)

    def test_distinct_platform_ids_preserve_identical_bubbles(self):
        crm.record_events(self.db, [event(event_id="message-1"), event(event_id="message-2")])
        self.assertEqual(self.report()["metrics"]["outbound_bubbles"], 2)
        self.assertEqual(self.report()["metrics"]["messages_sent_unique_contacts"], 1)

    def test_collision_rolls_back_whole_batch(self):
        crm.record_events(self.db, [event(event_id="message-1")])
        with self.assertRaises(ValueError):
            crm.record_events(self.db, [event(lead_key="second"), event(event_id="message-1", message_text="different")])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        self.assertIsNone(crm.get_lead(self.db, "second")["lead"])

    def test_legacy_database_is_not_modified(self):
        import hashlib
        path = Path(self.tmp.name) / "legacy.sqlite3"
        old = crm.connect(path)
        old.execute("PRAGMA user_version=0")
        old.close()
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        reopened = crm.connect(path)
        reopened.close()
        with crm.connect(path, readonly=True) as readonly:
            self.assertTrue(crm.eod_report(readonly, "2026-09-03")["coverage"]["legacy_reconciliation_required"])
        readonly.close()
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_legacy_ingestion_appends_without_rewriting_history(self):
        crm.record_events(self.db, [event()])
        self.db.execute("UPDATE events SET event_id='legacy-id'")
        self.db.execute("PRAGMA user_version=0")
        self.db.commit()
        old = dict(self.db.execute("SELECT * FROM events WHERE event_id='legacy-id'").fetchone())
        crm.record_events(self.db, [event(evidence_state="verified"), event(evidence_state="verified")])
        self.assertEqual(dict(self.db.execute("SELECT * FROM events WHERE event_id='legacy-id'").fetchone()), old)
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 2)
        self.assertEqual(self.report()["metrics"]["outbound_bubbles"], 1)
        self.assertEqual(crm.normalized_events(self.db)[0][0]["evidence_state"], "verified")

    def test_legacy_unknown_dates_remain_unresolved(self):
        crm.record_events(self.db, [event()])
        self.db.execute("UPDATE events SET occurred_at='2026-09-03',event_id='legacy-id'")
        self.db.execute("PRAGMA user_version=0")
        self.db.commit()
        report = self.report()
        self.assertEqual(report["metrics"]["outbound_bubbles"], 0)
        self.assertEqual(report["coverage"]["events_with_unknown_date"], 1)

    def test_readonly_missing_database_does_not_create_it(self):
        import sqlite3
        path = Path(self.tmp.name) / "missing.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):
            crm.connect(path, readonly=True)
        self.assertFalse(path.exists())

    def test_raw_message_is_never_stored_and_nine_fields_remain(self):
        crm.record_events(self.db, [event(message_text="synthetic private message")])
        self.assertNotIn("synthetic private message", "\n".join(self.db.iterdump()))
        self.assertEqual(len(self.report()["form"]), 9)

    def test_schema_tracks_event_fields(self):
        import json
        schema = json.loads((Path(__file__).parents[1] / "assets" / "crm-event.schema.json").read_text(encoding="utf-8"))
        self.assertIn("event_id", schema["properties"])
        self.assertEqual(set(schema["properties"]["event_type"]["enum"]), crm.EVENT_TYPES)
        self.assertEqual(set(schema["properties"]["evidence_state"]["enum"]), crm.EVIDENCE_STATES)

    def test_forward_conversation_with_partial_external_coverage(self):
        # Independent journey: multiple bubbles, later reply, followup and draft.
        crm.record_events(self.db, [
            event(event_id="a1"), event(event_id="a2", occurred_at="2026-09-03T10:01:00-03:00"),
            event(event_type="inbound_received", actor="lead", occurred_at="2026-09-03T11:00:00-03:00"),
            event(lead_key="followup", event_type="followup_sent"),
            event(lead_key="draft-only", event_type="dm_drafted", evidence_state="draft"),
            event(lead_key="new-inbound", event_type="inbound_received", actor="lead"),
        ])
        report = self.report()
        self.assertEqual(report["metrics"]["messages_sent_unique_contacts"], 2)
        self.assertEqual(report["metrics"]["outbound_bubbles"], 3)
        self.assertEqual(report["metrics"]["responded_same_day_cohort"], 1)
        self.assertEqual(report["metrics"]["late_responses"], 0)
        self.assertEqual(sum(report["quality"].values()), 3)
        self.assertEqual(report["coverage"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
