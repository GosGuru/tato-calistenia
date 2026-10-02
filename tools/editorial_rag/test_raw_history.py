"""Invented data only; no provider calls."""
import json
import unittest
from dataclasses import replace
from pathlib import Path

from tools.editorial_rag.raw_history import (  # pyright: ignore[reportMissingImports]
    RawHistoryPacket,
    parse_raw_result,
    raw_prompt,
)
from tools.editorial_rag.real_history import (  # pyright: ignore[reportMissingImports]
    MAX_GUIDANCE,
    RULE_PATHS,
    load_real_rules,
)


class RawHistoryTests(unittest.TestCase):
    def test_history_preserved_and_rules_complete(self):
        history = '  Export ficticio\r\nAutor desconocido\r\ntexto repetido\r\ntexto repetido\t🪁\r'
        rules = load_real_rules()
        prompt = raw_prompt(RawHistoryPacket(history, rules, True))
        self.assertEqual(json.loads(prompt.split('UNTRUSTED RAW HISTORY JSON\n')[1]), {'history': history})
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(len(RULE_PATHS), 7)
        for path in RULE_PATHS:
            self.assertIn((root / path).read_bytes().decode('utf-8'), prompt)
        for instruction in ('untrusted data', 'needs_context', 'Do not use tools', 'never infer authors', 'platform notices'):
            self.assertIn(instruction, prompt)
        self.assertNotIn('voice_guidance', prompt)

    def test_clarification_requires_material_unresolvable_ambiguity(self):
        prompt = raw_prompt(RawHistoryPacket('fragmento ficticio sin etiquetas', 'synthetic rules', True))
        for instruction in (
            'Only use needs_context for ambiguity that materially changes the safe next DM',
            'cannot be handled through a normal conversational response',
            'Absent labels or uncertain authorship of irrelevant historical messages do not justify clarification',
            'Reason cautiously from message content and context',
            'Ordinary missing qualification facts belong in a normal DM question',
        ):
            self.assertIn(instruction, prompt)

    def test_repeated_export_is_not_evidence_of_additional_outreach(self):
        export = 'export ficticio\r\nmensaje reiterado\r\nmensaje reiterado\r\n'
        history = export + export
        prompt = raw_prompt(RawHistoryPacket(history, 'synthetic rules', True))
        self.assertEqual(json.loads(prompt.split('UNTRUSTED RAW HISTORY JSON\n')[1]), {'history': history})
        for instruction in (
            'Distinguish a potentially repeated whole-export paste from additional actual contacts or follow-ups',
            'Never count duplicated export text as new outreach or invent recency',
            'Never discard genuinely repeated messages',
        ):
            self.assertIn(instruction, prompt)

    def test_server_guidance_is_bounded_conditional_and_not_lead_evidence(self):
        guidance = dict.fromkeys((
            'phase', 'gate', 'situation', 'last_assistant_move', 'proposed_move',
            'positive_voice', 'negative_repetition'), 'fictional condition')
        packet = RawHistoryPacket('unchanged fictional history', 'seven complete rules', True, (guidance,))
        prompt = raw_prompt(packet)
        for phrase in ('CONDITIONS, NEVER evidence', 'solely from actual history',
                       'Safety, motor, offer', 'Do not cite sources', 'not confidence'):
            self.assertIn(phrase, prompt)
        self.assertIn('seven complete rules', prompt)
        self.assertEqual(json.loads(prompt.split('UNTRUSTED RAW HISTORY JSON\n')[1]), {'history': packet.history})
        for invalid in ((guidance,) * (MAX_GUIDANCE + 1), ({**guidance, 'owner_id': 'fictional'},),
                        ({**guidance, 'phase': 'x' * 2001},), [guidance]):
            with self.assertRaises(ValueError):
                raw_prompt(replace(packet, guidance=invalid))

    def test_guidance_ceiling_accepts_max_and_rejects_one_more(self):
        guidance = dict.fromkeys((
            'phase', 'gate', 'situation', 'last_assistant_move', 'proposed_move',
            'positive_voice', 'negative_repetition'), 'fictional condition')
        self.assertEqual(MAX_GUIDANCE, 8)
        accepted = RawHistoryPacket('fictional history', 'synthetic rules', True,
                                    (guidance,) * MAX_GUIDANCE)
        accepted.validate()
        prompt = raw_prompt(accepted)
        guidance_json = prompt.split('CONDITIONAL GUIDANCE JSON\n')[1].split('\n')[0]
        self.assertEqual(len(json.loads(guidance_json)), MAX_GUIDANCE)
        with self.assertRaises(ValueError):
            raw_prompt(replace(accepted, guidance=(guidance,) * (MAX_GUIDANCE + 1)))

    def test_packet_strict_and_unicode_bounded(self):
        packet = RawHistoryPacket('🪁' * 24000, 'synthetic rules', True)
        packet.validate()
        for key, values in {'history': ['', '  ', None, 1, [], '\ud800', 'x\x00', 'x' * 24001],
                            'current_rules': ['', None, 1], 'consent': [False, 1, 'true', None]}.items():
            for value in values:
                with self.subTest(key=key, value_type=type(value)), self.assertRaises(ValueError):
                    raw_prompt(replace(packet, **{key: value}))
        with self.assertRaises(ValueError):
            raw_prompt({'history': 'fiction'})

    def test_result_exact_union_and_duplicate_keys(self):
        for value in ({'type': 'dm', 'text': 'salida inventada?'},
                      {'type': 'needs_context', 'question': 'quién escribió la última línea?'}):
            self.assertEqual(parse_raw_result(json.dumps(value)), value)
        invalid = [None, {}, 'texto', '{}', '[]', 'null', '```json\n{}\n```',
                   '{"type":"dm","type":"dm","text":"a"}',
                   '{"type":"dm","text":"a","text":"b"}']
        invalid += [json.dumps(value) for value in (
            {'type': 'dm', 'text': ' '}, {'type': 'dm', 'text': 1},
            {'type': 'dm', 'text': '\ud800'}, {'type': 'dm', 'text': 'x' * 24001},
            {'type': 'needs_context', 'question': ''}, {'type': 'needs_context', 'text': 'x'},
            {'type': 'dm', 'text': 'x', 'question': 'x'}, {'type': 'other', 'text': 'x'},
            {'type': 'dm', 'text': 'x', 'extra': True})]
        for output in invalid:
            with self.subTest(output_type=type(output)), self.assertRaises(ValueError):
                parse_raw_result(output)
