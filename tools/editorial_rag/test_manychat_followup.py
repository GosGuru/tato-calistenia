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
)


class FollowupEngineStaticTests(unittest.TestCase):
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

    def test_context_safety_override(self):
        import asyncio
        from .followup_engine import evaluate_lead_llm

        lead = LeadRecord(
            id="diego_1",
            name="Diego Castro",
            tags=[],
            messages=[
                LeadMessage(sender="lead", text="Total"),
            ],
        )
        # Model claims insufficient history/incoming message
        mock_output = '{"eligible": false, "reason": "Historial insuficiente o ambiguo: solo hay un mensaje del prospecto (\'Total\') sin contexto de conversación.", "followup_number": 0, "draft": ""}'

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
                {"id": "lead_1", "draft": "Buenas Alberto, ¿pudiste probar las anillas?"}
            ],
        }
        res = self.client.post("/api/manychat/send-batch", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        self.assertEqual(data["results"][0]["status"], "sent")
