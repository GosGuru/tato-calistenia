"""Invented blocks only; no provider calls."""
import json
import unittest
from dataclasses import replace

from tools.editorial_rag.organization import (  # pyright: ignore[reportMissingImports]
    OrganizationPacket,
    organization_prompt,
    parse_assignments,
    parse_blocks,
)


def blocks():
    return [{'id': 'm-1', 'text': 'pregunta ficticia?', 'role': 'assistant', 'time_context': 'Monday 10:30'},
            {'id': 'm-2', 'text': 'respuesta ficticia', 'role': 'unknown', 'time_context': None}]


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.packet = OrganizationPacket(parse_blocks(blocks()), True, True)
        self.output = {'assignments': [{'id': 'm-1', 'role': 'assistant', 'uncertain': False},
                                       {'id': 'm-2', 'role': 'unknown', 'uncertain': True}]}

    def test_prompt_and_valid_output(self):
        prompt = organization_prompt(self.packet)
        self.assertIn('untrusted', prompt)
        self.assertIn('user means the incoming prospect', prompt)
        self.assertIn('assistant means outgoing Tato', prompt)
        self.assertIn('Names or notices alone do not identify the sender', prompt)
        self.assertIn('Monday 10:30', prompt)
        self.assertNotIn('CURRENT RULES', prompt)
        self.assertEqual(parse_assignments(json.dumps(self.output), self.packet), self.output)

    def test_input_closed_bounded_and_consent(self):
        bad = [None, {}, [], blocks() * 51, [blocks()[0]] * 2]
        for key, value in [('id', ''), ('id', 'x' * 65), ('id', 1), ('role', 'system'),
                           ('text', ''), ('text', 'x' * 4001), ('text', '\ud800'),
                           ('time_context', 1), ('time_context', 'x' * 201), ('extra', True)]:
            bad.append([blocks()[0] | {key: value}])
        for value in bad:
            with self.assertRaises(ValueError):
                parse_blocks(value)
        for key in ('reviewed', 'consent'):
            for value in (False, 1, 'true', None):
                with self.assertRaises(ValueError):
                    organization_prompt(replace(self.packet, **{key: value}))

    def test_rejects_any_partial_rewrite_extra_or_changed_explicit_role(self):
        entries = self.output['assignments']
        bad = ['', '```json\n' + json.dumps(self.output) + '\n```', 'null', '{}', '[]',
               '{"assignments":[],"assignments":[]}', json.dumps(self.output) + '{}']
        values = [{'assignments': entries[::-1]}, {'assignments': entries[:1]},
                  {'assignments': entries + [entries[0]]}, self.output | {'text': 'rewrite'}]
        for change in ({'id': 'other'}, {'role': 'user'}, {'uncertain': 0}, {'text': 'rewrite'}):
            values.append({'assignments': [entries[0] | change, entries[1]]})
        values.append({'assignments': [entries[0], entries[1] | {'uncertain': False}]})
        bad += [json.dumps(v) for v in values]
        for value in bad:
            with self.assertRaisesRegex(ValueError, '^Organización no válida\\.$'):
                parse_assignments(value, self.packet)

    def test_known_proposal_can_remain_uncertain(self):
        self.output['assignments'][1] = {'id': 'm-2', 'role': 'user', 'uncertain': True}
        self.assertEqual(parse_assignments(json.dumps(self.output), self.packet), self.output)
