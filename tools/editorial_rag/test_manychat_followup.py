"""Tests for isolated ManyChat followup engine and API endpoints."""
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from . import local_web as web
from .followup_engine import (
    LeadMessage,
    LeadRecord,
    clean_draft_line,
    count_consecutive_tato_followups,
    evaluate_lead_static,
)


class FollowupEngineStaticTests(unittest.TestCase):
    def test_disqualifying_tags(self):
        lead = LeadRecord(
            id="1",
            name="Test",
            tags=["NO CALIFICA"],
            messages=[LeadMessage(sender="lead", text="hola")],
        )
        res = evaluate_lead_static(lead)
        self.assertIsNotNone(res)
        self.assertFalse(res.eligible)
        self.assertIn("etiqueta", res.reason.lower())

    def test_two_followups_exhausted(self):
        lead = LeadRecord(
            id="2",
            name="Test 2",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="cuanto sale?"),
                LeadMessage(sender="tato", text="Depende del tiempo. Que buscas?"),
                LeadMessage(sender="tato", text="Buenas, viste el mensaje?"),
            ],
        )
        self.assertEqual(count_consecutive_tato_followups(lead.messages), 2)
        res = evaluate_lead_static(lead)
        self.assertIsNotNone(res)
        self.assertFalse(res.eligible)
        self.assertIn("límite", res.reason.lower())

    def test_explicit_rejection(self):
        lead = LeadRecord(
            id="3",
            name="Test 3",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="No me interesa tu propuesta, gracias"),
            ],
        )
        res = evaluate_lead_static(lead)
        self.assertIsNotNone(res)
        self.assertFalse(res.eligible)
        self.assertIn("rechazo", res.reason.lower())

    def test_clean_draft_line(self):
        self.assertEqual(clean_draft_line("hola que tal"), "hola que tal?")
        self.assertEqual(clean_draft_line("linea 1\nlinea 2?"), "linea 1 linea 2?")
        self.assertEqual(clean_draft_line('"pudiste ver el cal.com?"'), "pudiste ver el cal.com?")


class ManyChatApiTests(unittest.TestCase):
    def setUp(self):
        self.app = web.create_app()
        self.client = TestClient(self.app, base_url=web.ORIGIN)
        self.token = web._TOKEN
        self.headers = {"Origin": web.ORIGIN, "X-CSRF-Token": self.token}

    def test_status_endpoint(self):
        res = self.client.get("/api/manychat/status", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("active", data)
        self.assertIn("logged_in", data)

    def test_scan_endpoint_mock(self):
        payload = {"mock": True, "date_filter": "septiembre", "limit": 10}
        res = self.client.post("/api/manychat/scan", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("leads", data)
        self.assertGreaterEqual(len(data["leads"]), 4)

        # Lead 3 has 2 follow-ups -> should be ineligible
        lead_3 = next(l for l in data["leads"] if l["id"] == "lead_3")
        self.assertFalse(lead_3["eligible"])

        # Lead 4 has NO CALIFICA -> should be ineligible
        lead_4 = next(l for l in data["leads"] if l["id"] == "lead_4")
        self.assertFalse(lead_4["eligible"])

    def test_send_batch_endpoint_mock(self):
        payload = {
            "mock": True,
            "leads": [
                {"id": "lead_1", "draft": "Buenas Alberto, ¿pudiste probar las anillas?"}
            ],
        }
        res = self.client.post("/api/manychat/send-batch", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        self.assertEqual(data["results"][0]["status"], "sent")
