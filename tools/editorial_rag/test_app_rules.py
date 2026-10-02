"""App prompt pack contracts. Fictional content only; no model or judge calls."""
import ast
import hashlib
import json
import re
import unittest
from pathlib import Path

from tools.editorial_rag.app_rules import (  # pyright: ignore[reportMissingImports]
    BASE_PATH,
    CARDS_PATH,
    MAX_PASSAGE_CHARACTERS,
    OPAQUE_FIELDS,
    _cards_from_data,
    load_app_cards,
    load_app_rules,
)
from tools.editorial_rag.editorial_criteria import (  # pyright: ignore[reportMissingImports]
    criterion_passage,
)
from tools.editorial_rag.prototype import Card  # pyright: ignore[reportMissingImports]
from tools.editorial_rag.real_history import (  # pyright: ignore[reportMissingImports]
    load_real_rules,
)

ROOT = Path(__file__).resolve().parents[2]
INVARIANTS_PATH = ROOT / 'tools' / 'editorial_rag' / 'app_rules' / 'invariants.md'
LOADER_PATH = Path(__file__).resolve().parent / 'app_rules.py'
SKILL_ROOT = '.agents/skills/tato-calistenia/'
MAX_BASE_CHARACTERS = 25_000
# Snapshot of load_real_rules() taken before this pack existed. The seven normative
# sources are frozen for the offline bank, so the joined output must not drift.
RULES_SHA256_PRE_TASK = '3928b817d5717c6f797ea832f6c33602678fe1449769ded93a4af62459051b51'
RULES_CHARACTERS_PRE_TASK = 114_214
EXPECTED_INVARIANTS = 63
EXPECTED_THEMES = {'format', 'voice_contract', 'offer_agenda',
                   'safety_health', 'sequence_conversion'}
OPAQUE_IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9_-]{0,79}')
PACK_IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,79}')


def _inventory() -> dict:
    text = INVARIANTS_PATH.read_text(encoding='utf-8')
    block = text.split('```json', 1)[1].split('```', 1)[0]
    return json.loads(block)


def _source_lines(source: str) -> list:
    if not source.startswith(SKILL_ROOT) or '..' in source:
        raise AssertionError('citation outside the normative skill references: ' + source)
    return (ROOT / source).read_text(encoding='utf-8').replace('\r\n', '\n').split('\n')


class InvariantInventoryTests(unittest.TestCase):
    """Safety guarantee: every invariant stays pinned to its cited source location."""

    def test_inventory_is_well_formed_and_pinned_to_sources(self):
        invariants = _inventory()['invariants']
        self.assertEqual(len(invariants), EXPECTED_INVARIANTS)
        ids = [entry['id'] for entry in invariants]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in invariants:
            with self.subTest(invariant=entry['id']):
                self.assertRegex(entry['id'], PACK_IDENTIFIER)
                self.assertIn(entry['theme'], EXPECTED_THEMES)
                self.assertGreaterEqual(len(entry['citations']), 1)
                for citation in entry['citations']:
                    self.assertEqual(set(citation), {'source', 'lines', 'quote'})
                    lines = _source_lines(citation['source'])
                    start, end = citation['lines']
                    self.assertIs(type(start), int)
                    self.assertIs(type(end), int)
                    self.assertGreaterEqual(start, 1)
                    self.assertGreaterEqual(end, start)
                    self.assertLessEqual(end, len(lines))
                    slice_text = '\n'.join(line.rstrip() for line in lines[start - 1:end])
                    self.assertIn(citation['quote'], slice_text)

    def test_every_invariant_appears_in_the_base_prompt(self):
        base = load_app_rules()
        for entry in _inventory()['invariants']:
            with self.subTest(invariant=entry['id']):
                self.assertIn(entry['base_anchor'], base)


class LoaderIsolationTests(unittest.TestCase):
    """The app pack loader must never touch the local setter rule loader."""

    def test_loader_never_imports_the_local_rule_loader(self):
        source = LOADER_PATH.read_text(encoding='utf-8')
        self.assertNotIn('load_real_rules', source)
        self.assertNotIn('RULE_PATHS', source)
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or '')
                imported.extend(alias.name for alias in node.names)
        self.assertFalse(any('real_history' in name for name in imported))

    def test_load_real_rules_is_byte_identical_to_the_pre_task_snapshot(self):
        rules = load_real_rules()
        self.assertEqual(len(rules), RULES_CHARACTERS_PRE_TASK)
        self.assertEqual(hashlib.sha256(rules.encode('utf-8')).hexdigest(),
                         RULES_SHA256_PRE_TASK)


class CardPackTests(unittest.TestCase):
    """Schema, identifier and size contracts of cards.json."""

    def test_every_card_parses_and_passes_criterion_passage(self):
        cards = load_app_cards()
        self.assertGreaterEqual(len(cards), 8)
        self.assertLessEqual(len(cards), 12)
        for card in cards:
            with self.subTest(card=card.card_id):
                self.assertIs(type(card), Card)
                passage = criterion_passage(card)
                self.assertTrue(passage.strip())

    def test_every_card_passage_stays_under_the_conservative_bound(self):
        for card in load_app_cards():
            with self.subTest(card=card.card_id):
                self.assertLess(len(criterion_passage(card)), MAX_PASSAGE_CHARACTERS)

    def test_card_identifiers_are_opaque(self):
        for card in load_app_cards():
            with self.subTest(card=card.card_id):
                self.assertRegex(card.card_id, PACK_IDENTIFIER)
                self.assertRegex(card.provenance_id, PACK_IDENTIFIER)
                for name in OPAQUE_FIELDS[2:]:
                    self.assertRegex(getattr(card, name), OPAQUE_IDENTIFIER)

    def test_card_situations_are_descriptive_prose(self):
        """Retrieval regression: a slug situation is silently dropped by retrieve()."""
        for card in load_app_cards():
            with self.subTest(card=card.card_id):
                self.assertIn(' ', card.situation)
                self.assertGreater(len(card.situation.split()), 5)
                self.assertIsNone(OPAQUE_IDENTIFIER.fullmatch(card.situation))
                self.assertIn('Aplica cuando ', card.situation)
                self.assertIn('No aplica cuando ', card.situation)

    def test_malformed_cards_are_rejected_loudly(self):
        good = json.loads(CARDS_PATH.read_text(encoding='utf-8'))[0]
        cases = {
            'not-a-list': {'card_id': 'x'},
            'empty-list': [],
            'item-not-object': [good, 'texto'],
            'missing-field': {k: v for k, v in good.items() if k != 'positive_voice'},
            'extra-field': dict(good, invented='x'),
            'bad-card-id': dict(good, card_id='Card 1'),
            'bad-status': dict(good, status='pending'),
            'not-sanitized': dict(good, sanitized=False),
            'bad-phase': dict(good, phase='fase'),
            'empty-text': dict(good, negative_repetition='  '),
            'nul-byte': dict(good, positive_voice='hola\x00'),
            'over-field-limit': dict(good, situation='a' * (2000 + 1)),
            'duplicate-id': [good, dict(good)],
        }
        for name, payload in cases.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                _cards_from_data(payload)

    def test_base_prompt_fits_the_ceiling_and_holds_the_output_contract(self):
        base = load_app_rules()
        self.assertEqual(base, BASE_PATH.read_text(encoding='utf-8'))
        self.assertLess(len(base), MAX_BASE_CHARACTERS)
        self.assertIn('{"type":"dm","text":"..."}', base)
        self.assertIn('{"type":"needs_context","question":"..."}', base)
        self.assertIn('https://cal.com/tato-ramon/reunion-auditoria', base)
        self.assertIn('USD 300', base)
        self.assertIn('Voseo rioplatense', base)
