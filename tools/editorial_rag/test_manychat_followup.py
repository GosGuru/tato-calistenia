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
    extract_first_name,
    is_recent_activity,
)
from .followup_ledger import FollowupLedger, fup_number_from_tags, get_ledger


class FollowupEngineStaticTests(unittest.TestCase):
    def test_recent_activity_rejection(self):
        self.assertTrue(is_recent_activity("7min"))
        self.assertTrue(is_recent_activity("40min"))
        self.assertTrue(is_recent_activity("1h"))
        self.assertTrue(is_recent_activity("ahora"))
        self.assertFalse(is_recent_activity("1d"))
        self.assertFalse(is_recent_activity("15 de septiembre"))
        self.assertFalse(is_recent_activity("ayer"))

        lead = LeadRecord(
            id="rec_1",
            name="Alejandro Cordoba",
            last_date="7min",
            messages=[LeadMessage(sender="lead", text="hola")],
        )
        res = evaluate_lead_static(lead)
        self.assertIsNotNone(res)
        self.assertFalse(res.eligible)
        self.assertIn("reciente", res.reason.lower())
    def test_extract_first_name(self):
        self.assertEqual(extract_first_name("Axel Gomez"), "Axel")
        self.assertEqual(extract_first_name("Roberto Carlos Saavedra Rivera"), "Roberto")
        self.assertEqual(extract_first_name("Diego Castro"), "Diego")
        self.assertEqual(extract_first_name("Julieta R"), "Julieta")
        self.assertEqual(extract_first_name("🔥 Axel Gomez 🔥"), "Axel")
        self.assertEqual(extract_first_name("@axel_gomez"), "Axel")
        self.assertIsNone(extract_first_name("usuario_123"))
        self.assertIsNone(extract_first_name(""))

    def test_clean_draft_line(self):
        self.assertEqual(clean_draft_line("hola que tal"), "hola que tal?")
        self.assertEqual(clean_draft_line("linea 1\nlinea 2?"), "linea 1 linea 2?")
        self.assertEqual(clean_draft_line('"pudiste ver el cal.com?"'), "pudiste ver el cal.com?")
        # Holly sequence rules: no opening ¿, emoji preserved
        self.assertEqual(clean_draft_line("¿Axel?"), "Axel?")
        self.assertEqual(clean_draft_line("¿Querés que veamos eso?"), "Querés que veamos eso?")
        self.assertEqual(clean_draft_line("🙃"), "🙃")
        self.assertEqual(clean_draft_line("🙃?"), "🙃")
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

    def test_evaluate_lead_llm_fup1_holly(self):
        import asyncio
        from .followup_engine import evaluate_lead_llm

        lead = LeadRecord(
            id="axel_1",
            name="Axel Gomez",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="Hola Tato, quiero entrenar"),
                LeadMessage(sender="tato", text="Claro Axel, como venis entrenando hoy?"),
            ],
        )
        mock_output = '{"eligible": true, "reason": "Ghosteo tras pregunta", "followup_number": 1, "draft": "¿Querés que veamos juntos cómo aplicar esos isométricos?"}'

        with patch("tools.editorial_rag.followup_engine.create_runner") as mock_create:
            mock_runner = AsyncMock(return_value=mock_output)
            mock_create.return_value = mock_runner
            res = asyncio.run(evaluate_lead_llm(lead))
            self.assertTrue(res.eligible)
            self.assertEqual(res.followup_number, 1)
            # Enforces Holly sequence: Axel? instead of the model's paragraph pitch
            self.assertEqual(res.draft, "Axel?")

    def test_evaluate_lead_llm_fup2_holly(self):
        import asyncio
        from .followup_engine import evaluate_lead_llm

        lead = LeadRecord(
            id="axel_1",
            name="Axel Gomez",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="Hola Tato"),
                LeadMessage(sender="tato", text="Axel?"),
            ],
        )
        mock_output = '{"eligible": true, "reason": "Segundo seguimiento", "followup_number": 2, "draft": "avísame si querés retomar?"}'
        with patch("tools.editorial_rag.followup_engine.create_runner") as mock_create:
            mock_runner = AsyncMock(return_value=mock_output)
            mock_create.return_value = mock_runner
            res = asyncio.run(evaluate_lead_llm(lead))
            self.assertTrue(res.eligible)
            self.assertEqual(res.followup_number, 2)
            self.assertEqual(res.draft, "🙃")

    def test_extract_first_name_advanced(self):
        self.assertEqual(extract_first_name("~𝑨𝒍𝒗𝒂𝒓𝒐 𝑻𝒐𝒎𝒂𝒔~"), "Alvaro")
        self.assertEqual(extract_first_name("benjaa.ibanez01"), "Benja")
        self.assertIsNone(extract_first_name("no te enteres"))
        self.assertEqual(extract_first_name("Vicente Gómez Lucas"), "Vicente")

    def test_fup2_exhausted_static(self):
        lead = LeadRecord(
            id="natalia_1",
            name="Natalia Karina Altolaguirre",
            tags=[],
            messages=[
                LeadMessage(sender="tato", text="🙃"),
            ],
        )
        res = evaluate_lead_static(lead)
        self.assertIsNotNone(res)
        self.assertFalse(res.eligible)
        self.assertIn("límite", res.reason.lower())

    def test_inbound_message_strictly_ineligible(self):
        lead = LeadRecord(
            id="diego_1",
            name="Diego Castro",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="Hola Tato, me interesa"),
            ],
        )
        res = evaluate_lead_static(lead)
        self.assertIsNotNone(res)
        self.assertFalse(res.eligible)
        self.assertIn("prospecto", res.reason.lower())

    def test_context_safety_override(self):
        import asyncio
        from .followup_engine import evaluate_lead_llm

        lead = LeadRecord(
            id="diego_1",
            name="Diego Castro",
            tags=[],
            messages=[
                LeadMessage(sender="tato", text="Hola Diego, cómo venís entrenando hoy?"),
            ],
        )
        # Model claims insufficient history
        mock_output = '{"eligible": false, "reason": "Historial insuficiente o ambiguo: solo hay un mensaje sin contexto previo.", "followup_number": 0, "draft": ""}'

        with patch("tools.editorial_rag.followup_engine.create_runner") as mock_create:
            mock_runner = AsyncMock(return_value=mock_output)
            mock_create.return_value = mock_runner
            res = asyncio.run(evaluate_lead_llm(lead))
            # Must override to eligible = True and produce Diego?
            self.assertTrue(res.eligible)
            self.assertEqual(res.followup_number, 1)
            self.assertEqual(res.draft, "Diego?")




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
                {"id": "lead_1", "draft": "Buenas Alberto, ¿pudiste probar las anillas?", "followup_number": 1}
            ],
        }
        res = self.client.post("/api/manychat/send-batch", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        self.assertEqual(data["results"][0]["status"], "sent")
        self.assertEqual(data["results"][0]["followup_number"], 1)

        # Verify ledger recorded the entry
        ledger = get_ledger()
        entry = ledger.get("lead_1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["fup"], 1)


class FollowupLedgerTests(unittest.TestCase):
    def test_fup_tag_parsing(self):
        self.assertEqual(fup_number_from_tags(["FUP 1"]), 1)
        self.assertEqual(fup_number_from_tags(["fup-2"]), 2)
        self.assertEqual(fup_number_from_tags(["FOP 1", "FUP 2"]), 2)
        self.assertEqual(fup_number_from_tags(["seguimiento 3"]), 3)
        self.assertEqual(fup_number_from_tags(["interesado", "anillas"]), 0)
        self.assertEqual(fup_number_from_tags([]), 0)

    def test_ledger_cooldown_window(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            ledger = FollowupLedger(Path(td) / "test-ledger.json")
            now = 100000.0

            ledger.record_sent("chat_1", 1, "Axel?", now=now)
            ledger.record_sent("chat_2", 2, "🙃", now=now - 25000)  # ~7h ago

            # 6 hour cooldown: chat_1 (<6h) is cooling down, chat_2 (7h ago) is past 6h
            cooling = ledger.cooling_down_ids(cooldown_hours=6.0, now=now)
            self.assertIn("chat_1", cooling)
            self.assertNotIn("chat_2", cooling)

            # Prior follow-up check: matches text
            self.assertEqual(ledger.prior_followup("chat_1", "Axel?"), 1)
            # If Tato's last message is something else (or lead spoke), it returns 0
            self.assertEqual(ledger.prior_followup("chat_1", "otro mensaje"), 0)

    def test_lead_with_prior_fup_advances_to_fup2(self):
        import asyncio
        from .followup_engine import evaluate_lead_llm

        lead = LeadRecord(
            id="fup1_lead",
            name="Claudio Ramos",
            prior_fup=1,
            tags=["FUP 1"],
            messages=[
                LeadMessage(sender="lead", text="hola tato"),
                LeadMessage(sender="tato", text="Claudio?"),
            ],
        )
        mock_output = '{"eligible": true, "reason": "silencio", "followup_number": 1, "draft": "Claudio?"}'
        with patch("tools.editorial_rag.followup_engine.create_runner") as mock_create:
            mock_runner = AsyncMock(return_value=mock_output)
            mock_create.return_value = mock_runner
            res = asyncio.run(evaluate_lead_llm(lead))
            self.assertTrue(res.eligible)
            self.assertEqual(res.followup_number, 2)
            self.assertEqual(res.draft, "🙃")

    def test_lead_with_prior_fup2_is_disqualified(self):
        lead = LeadRecord(
            id="fup2_lead",
            name="Claudio Ramos",
            prior_fup=2,
            tags=["FUP 2"],
            messages=[
                LeadMessage(sender="lead", text="hola tato"),
                LeadMessage(sender="tato", text="🙃"),
            ],
        )
        res = evaluate_lead_static(lead)
        self.assertIsNotNone(res)
        self.assertFalse(res.eligible)
        self.assertIn("límite", res.reason.lower())
