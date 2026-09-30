"""Synthetic-only contracts; no production conversations or editorial corpus."""
import unittest
from dataclasses import replace
from unittest.mock import patch

from prototype import Card, Conversation, Message, compare, packets, retrieve


def card(**changes):
    values = dict(card_id="direct", provenance_id="curation-001", status="approved",
                  sanitized=True, phase="brecha", gate="normal", situation="respuesta breve",
                  last_assistant_move="validation", proposed_move="question",
                  positive_voice="Priorizar una pregunta concreta cuando basta.",
                  negative_repetition="Evitar una segunda validación automática.")
    return Card(**(values | changes))


def conversation(**changes):
    values = dict(sanitized=True, phase="brecha", gate="normal",
                  situation="respuesta breve", last_assistant_move="validation",
                  messages=(Message("assistant", "bien ahí, seguí contando"),
                            Message("user", "sí")))
    return Conversation(**(values | changes))


class PrototypeTests(unittest.TestCase):
    def test_short_reply_penalizes_repeated_validation(self):
        repeated = card(card_id="repeat", proposed_move="validation")
        self.assertEqual(retrieve((repeated, card()), conversation()).card_id, "direct")

    def test_unapproved_wrong_gate_phase_and_no_match(self):
        for change in ({"status": "candidate"}, {"status": "rejected"},
                       {"phase": "ruta"}, {"gate": "closure"},
                       {"situation": "otra señal"}):
            self.assertIsNone(retrieve((card(**change),), conversation()))
        self.assertIsNone(retrieve((), conversation()))

    def test_deterministic_tie(self):
        a, b = card(card_id="a"), card(card_id="b")
        self.assertEqual(retrieve((b, a), conversation()), retrieve((a, b), conversation()))

    def test_cross_lead_isolation_and_no_templates(self):
        first = conversation()
        second = conversation(messages=(Message("user", "contexto sintético distinto"),))
        packets(first, (card(),), "CURRENT RULES")
        baseline, editorial = packets(second, (card(),), "CURRENT RULES")
        self.assertNotIn("bien ahí", repr(editorial))
        self.assertEqual(baseline.conversation, editorial.conversation)
        self.assertIsNone(baseline.guidance)
        self.assertEqual(editorial.guidance.provenance_id, "curation-001")
        with self.assertRaises(TypeError):
            Card(**(card().__dict__ | {"raw_quote": "not permitted"}))

    def test_reject_unattested_or_malformed_inputs(self):
        for factory in (lambda: card(sanitized=False),
                        lambda: conversation(sanitized=False),
                        lambda: card(provenance_id="raw/chat.txt"),
                        lambda: conversation(messages="/raw/chat.txt"),
                        lambda: card(status="unknown"),
                        lambda: card(positive_voice="")):
            with self.assertRaises((ValueError, TypeError)):
                factory()

    def test_compare_only_mechanical_signals_no_io(self):
        outputs = iter(("bien ahí, seguí contando", "qué falta aclarar?"))
        def runner(packet):
            return next(outputs)
        with patch("builtins.open", side_effect=AssertionError("file IO")), \
             patch("socket.socket", side_effect=AssertionError("network")):
            result = compare(conversation(), (card(),), "CURRENT RULES", runner)
        self.assertTrue(result.current.exact_previous)
        self.assertTrue(result.current.same_opening)
        self.assertFalse(result.editorial.same_opening)
        self.assertNotIn("bien ahí", repr(result))
        self.assertFalse(hasattr(result, "approved"))

    def test_immediate_assistant_not_user_or_older_turn(self):
        c = conversation(messages=(Message("assistant", "old opening text"),
                                   Message("user", "intermediate"),
                                   Message("assistant", "new opening text"),
                                   Message("user", "old opening text")))
        result = compare(c, (), "rules", lambda _: "old opening text")
        self.assertFalse(result.current.exact_previous)
        self.assertFalse(result.current.same_opening)

    def test_no_card_packets_identical_except_variant(self):
        a, b = packets(conversation(), (), "rules")
        self.assertEqual(replace(a, variant="editorial"), b)


if __name__ == "__main__":
    unittest.main()
