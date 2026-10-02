"""Offline tests: embedding is always mocked; tokenization is local and real.

No model inference, network or database call happens here. The only real work is
tokenization through the pinned tokenizer.json of the local model cache, which is
the ceiling the embedder enforces and the thing this suite must measure.
"""
import ast
import copy
import hashlib
import json
import re
import struct
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from tools.editorial_rag import (  # pyright: ignore[reportMissingImports]
    prepare_card_seed as seed,
)
from tools.editorial_rag.app_rules import (  # pyright: ignore[reportMissingImports]
    load_app_cards,
)
from tools.editorial_rag.editorial_criteria import (  # pyright: ignore[reportMissingImports]
    MODEL_METADATA,
    criterion_passage,
)

VECTOR = [1.0] + [0.0] * 383
FILLER = 'Invented filler sentence for the offline ceiling test. '
# Real token counts of criterion_passage measured with the pinned tokenizer on
# passage: <passage> including special tokens (same as embed.mjs tokenLength).
EXPECTED_PACK_TOKENS = {
    'voice-reconocimiento-proporcional': 210,
    'voice-espejo-vocabulario': 227,
    'voice-puente-conectivo': 220,
    'voice-pregunta-directa': 203,
    'voice-escucha-visible': 203,
    'voice-autoridad-hecho': 205,
    'voice-reentrada-saludo': 189,
    'voice-ruta-contextual': 215,
    'tech-orientar-sin-corregir': 219,
    'tech-traduccion-corporal': 204,
    'voice-invitacion-calida': 229,
    'voice-objecion-dignidad': 223,
}


def build_cards(count):
    return [seed.Card(
        card_id=f'fixture_card_{index:02d}', provenance_id='fictional_fixture',
        status='candidate', sanitized=True, phase='ruta',
        gate='fictional_gate', situation=f'Invented puzzle scenario {index}.',
        last_assistant_move='ask_puzzle', proposed_move='clarify_piece',
        positive_voice=f'Consider the imaginary blue piece {index}.',
        negative_repetition=f'Repeat the fictional puzzle clue {index}.',
    ) for index in range(count)]


def snapshot_for(cards):
    return {
        'owner_id': seed.OWNER, 'count': len(cards),
        'fingerprints': {card.card_id: seed.fingerprint(seed.OWNER, card) for card in cards},
        'cards': [dict(asdict(card), owner_id=seed.OWNER, approval_id=None) for card in cards],
    }


def unit_vector(text):
    """Deterministic one-hot unit vector; distinct texts get distinct vectors."""
    vector = [0.0] * len(VECTOR)
    vector[int(hashlib.sha256(text.encode('utf-8')).hexdigest(), 16) % len(VECTOR)] = 1.0
    return vector


def embed_patch():
    """One deterministic unit vector per passage, batch-shaped like the real adapter."""
    return patch.object(seed.local_embedding, 'embed_passages',
                        side_effect=lambda texts: [unit_vector(text) for text in texts])


class SeedTests(unittest.TestCase):
    def test_fixture_setup_without_file_reads(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('fixture must not read files')):
            cards = seed.validate_snapshot(snapshot_for(build_cards(2)))
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(card.status == 'candidate' and card.sanitized for card in cards))

    def test_wire_sample(self):
        self.assertEqual(seed.vector_wire([1, 0, -0.5]).hex(), '000300003f80000000000000bf000000')

    def test_float32_roundtrip(self):
        for value in [0.0, -0.0, 1/3, 1e-38, -0.123456789, 1.17549435e-38]:
            self.assertEqual(struct.pack('>f', float(seed.vector_number(value))), struct.pack('>f', value))

    def test_exact_input_before_inference(self):
        cards = build_cards(2)
        data = snapshot_for(cards)
        cases = []
        for key, value in [('status', 'approved'), ('approval_id', 'old'), ('sanitized', False),
                           ('owner_id', 'bad'), ('positive_voice', 'changed')]:
            mutated = copy.deepcopy(data)
            mutated['cards'][1][key] = value
            cases.append(mutated)
        duplicated = copy.deepcopy(data)
        duplicated['cards'][1] = duplicated['cards'][0]
        cases.append(duplicated)
        extra = copy.deepcopy(data)
        extra['extra'] = True
        cases.append(extra)
        for data in cases:
            with self.subTest(data=list(data)), patch.object(seed.local_embedding, 'embed_passages') as embed:
                with self.assertRaises(seed.SeedError):
                    seed.prepare(data)
                embed.assert_not_called()

    def test_accepts_one_two_and_twelve_cards(self):
        for count in (1, 2, 12):
            with self.subTest(count=count):
                cards = build_cards(count)
                data = snapshot_for(cards)
                with embed_patch() as embed:
                    sql, report = seed.prepare(data)
                calls = [len(call.args[0]) for call in embed.call_args_list]
                self.assertEqual(sum(calls), count)
                self.assertTrue(all(size <= seed.MAX_EMBED_BATCH for size in calls))
                self.assertEqual(report['count'], count)
                self.assertEqual(len(report['cards']), count)
                self.assertEqual(report['dimensions'], MODEL_METADATA['dimensions'])
                self.assertEqual(report['model_metadata'], dict(MODEL_METADATA))
                self.assertEqual(report['status'], 'manual_review_only')
                self.assertEqual(report['sql_sha256'], hashlib.sha256(sql.encode('utf-8')).hexdigest())
                derived = {card.card_id: seed.fingerprint(seed.OWNER, card) for card in cards}
                self.assertEqual({row['card_id']: row['fingerprint'] for row in report['cards']}, derived)
                self.assertEqual(list(report['cards'][0]), ['card_id', 'fingerprint', 'vector_wire_sha256', 'norm'])
                wires = set()
                for card, row in zip(cards, report['cards'], strict=True):
                    wire = hashlib.sha256(seed.vector_wire(unit_vector(criterion_passage(card)))).hexdigest()
                    self.assertEqual(row['vector_wire_sha256'], wire)
                    self.assertAlmostEqual(row['norm'], 1.0, places=6)
                    wires.add(wire)
                self.assertEqual(len(wires), count)
                self.assertTrue(sql.endswith('COMMIT;\n'))
                self.assertIn('Manual review only', sql)
                self.assertIn('this plan is not authorization', sql)
                self.assertNotIn('ON CONFLICT', sql)
                for card in cards:
                    self.assertNotIn(card.positive_voice, sql)
                    self.assertNotIn(card.situation, sql)

    def test_sql_contains_n_card_guards_and_n_count_guards(self):
        for count in (1, 2, 12):
            with self.subTest(count=count):
                cards = build_cards(count)
                with embed_patch():
                    sql, report = seed.prepare(snapshot_for(cards))
                self.assertEqual(sql.count('Card content guard failed'), count)
                for card, row in zip(cards, report['cards'], strict=True):
                    # One guard block per card; fingerprint in guard, insert and
                    # the two aggregate VALUES joins; wire hash in both joins;
                    # card id in its guard, both id lists, insert and both joins.
                    self.assertEqual(sql.count(row['fingerprint']), 4)
                    self.assertEqual(sql.count(row['vector_wire_sha256']), 2)
                    self.assertEqual(sql.count(card.card_id), 6)
                self.assertIn(f"IF affected <> {count} THEN RAISE EXCEPTION 'Card update count failed'", sql)
                self.assertIn(f"IF affected <> {count} THEN RAISE EXCEPTION 'Embedding count failed'", sql)
                for label in ('Runtime readback failed', 'Vector wire guard failed'):
                    self.assertRegex(sql, rf"\) <> {count} THEN\s+RAISE EXCEPTION '{label}'")
                self.assertEqual(sql.count('Runtime readback failed'), 1)
                self.assertEqual(sql.count('Vector wire guard failed'), 1)

    def test_count_guards_reject_a_claimed_count_that_differs_from_the_content(self):
        for count in (2, 12):
            data = snapshot_for(build_cards(count))
            cases = []
            for claimed in (count + 1, count - 1, 0, seed.MAX_CARDS + 1):
                cases.append(dict(data, count=claimed))
            short_map = copy.deepcopy(data)
            del short_map['fingerprints'][short_map['cards'][0]['card_id']]
            cases.append(short_map)
            long_map = copy.deepcopy(data)
            long_map['fingerprints']['invented_extra'] = '0' * 64
            cases.append(long_map)
            long_cards = copy.deepcopy(data)
            long_cards['cards'] = long_cards['cards'] + long_cards['cards'][:1]
            cases.append(long_cards)
            for case in cases:
                with self.subTest(count=count, claimed=case['count']), \
                        patch.object(seed.local_embedding, 'embed_passages') as embed:
                    with self.assertRaises(seed.SeedError):
                        seed.prepare(case)
                    embed.assert_not_called()

    def test_fingerprints_are_derived_from_content_not_pinned(self):
        cards = build_cards(2)
        other = copy.deepcopy(snapshot_for(cards))
        changed = [asdict(card) for card in cards]
        changed[1]['positive_voice'] = 'Consider the imaginary red piece instead.'
        other['cards'] = [dict(card, owner_id=seed.OWNER, approval_id=None) for card in changed]
        other['fingerprints'] = {row['card_id']: seed.fingerprint(seed.OWNER, seed.Card(
            **{key: row[key] for key in seed.CARD_FIELDS})) for row in other['cards']}
        with embed_patch():
            sql_a, report_a = seed.prepare(snapshot_for(cards))
            sql_b, report_b = seed.prepare(other)
        self.assertNotEqual(report_a['cards'][1]['fingerprint'], report_b['cards'][1]['fingerprint'])
        self.assertEqual(report_a['cards'][0]['fingerprint'], report_b['cards'][0]['fingerprint'])
        self.assertNotEqual(sql_a, sql_b)
        self.assertNotEqual(report_a['sql_sha256'], report_b['sql_sha256'])
        for card, row in zip(cards, report_a['cards'], strict=True):
            self.assertEqual(row['fingerprint'], seed.fingerprint(seed.OWNER, card))
        self.assertNotEqual(report_a['cards'][0]['fingerprint'], report_a['cards'][1]['fingerprint'])
        # No pinned per-card fingerprint constant may exist in the tool source.
        source = Path(seed.__file__).read_text(encoding='utf-8')
        self.assertIsNone(re.search(r'\b[0-9a-f]{64}\b', source))

    def test_overlong_passage_is_rejected_before_inference(self):
        card = seed.Card(
            card_id='fixture_overlong', provenance_id='fictional_fixture',
            status='candidate', sanitized=True, phase='ruta', gate='fictional_gate',
            situation=FILLER * 35, last_assistant_move='ask_puzzle', proposed_move='clarify_piece',
            positive_voice=FILLER * 35, negative_repetition=FILLER * 35,
        )
        data = snapshot_for([card])
        self.assertGreater(seed.passage_tokens(criterion_passage(card)), seed.PASSAGE_TOKEN_CEILING)
        with patch.object(seed.local_embedding, 'embed_passages') as embed:
            with self.assertRaisesRegex(seed.SeedError, '^passage_too_long$'):
                seed.prepare(data)
            embed.assert_not_called()

    def test_pack_passages_fit_the_real_embedder_token_ceiling(self):
        cards = load_app_cards()
        self.assertEqual(len(cards), 12)
        self.assertEqual(seed.PASSAGE_TOKEN_CEILING, 512)
        for card in cards:
            with self.subTest(card=card.card_id):
                tokens = seed.passage_tokens(criterion_passage(card))
                self.assertEqual(tokens, EXPECTED_PACK_TOKENS[card.card_id])
                self.assertLessEqual(tokens, seed.PASSAGE_TOKEN_CEILING)

    def test_existing_outputs_prevent_inference_and_writes(self):
        for existing in (seed.PLAN_NAME, seed.REPORT_NAME, None):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'snapshot.json'
                snapshot.write_text(json.dumps(snapshot_for(build_cards(2))), encoding='utf-8')
                keep = Path(directory) / (existing or seed.PLAN_NAME)
                keep.write_text('keep', encoding='utf-8')
                with patch.object(seed.local_embedding, 'embed_passages') as embed, patch('builtins.print'):
                    result = seed.main(['--snapshot', str(snapshot), '--output-dir', directory])
                self.assertEqual(result, 1)
                self.assertEqual(keep.read_text(encoding='utf-8'), 'keep')
                if existing == seed.PLAN_NAME:
                    self.assertFalse((Path(directory) / seed.REPORT_NAME).exists())
                embed.assert_not_called()

    def test_cli_writes_fictional_artifacts_once(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'snapshot.json'
            data = snapshot_for(build_cards(12))
            snapshot.write_text(json.dumps(data), encoding='utf-8')
            with embed_patch() as embed, patch('builtins.print') as output:
                result = seed.main(['--snapshot', str(snapshot), '--output-dir', directory])
            self.assertEqual(result, 0)
            self.assertEqual(sum(len(call.args[0]) for call in embed.call_args_list), 12)
            sql = (Path(directory) / seed.PLAN_NAME).read_text(encoding='utf-8')
            report = json.loads((Path(directory) / seed.REPORT_NAME).read_text(encoding='utf-8'))
            self.assertEqual(set(report), {'count', 'dimensions', 'approval_id', 'model_metadata',
                                           'cards', 'sql_sha256', 'status'})
            self.assertEqual(report['count'], 12)
            self.assertEqual(report['status'], 'manual_review_only')
            self.assertEqual(report['sql_sha256'], hashlib.sha256(sql.encode('utf-8')).hexdigest())
            self.assertEqual({row['card_id']: row['fingerprint'] for row in report['cards']},
                             data['fingerprints'])
            for card in data['cards']:
                self.assertNotIn(card['positive_voice'], sql)
            self.assertEqual(json.loads(output.call_args.args[0])['count'], 12)
            # Second run in the same directory never overwrites the artifacts.
            before = (Path(directory) / seed.PLAN_NAME).read_bytes()
            with embed_patch(), patch('builtins.print'):
                self.assertEqual(seed.main(['--snapshot', str(snapshot), '--output-dir', directory]), 1)
            self.assertEqual((Path(directory) / seed.PLAN_NAME).read_bytes(), before)

    def test_strict_bounded_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            for raw in ['{"owner_id":1,"owner_id":2}', '{"x":NaN}',
                        ' ' * (seed.MAX_SNAPSHOT_BYTES + 1), '{"owner_id": "x", "count": 1, "fingerprint' ]:
                path.write_text(raw, encoding='utf-8')
                with self.assertRaises(seed.SeedError):
                    seed.load_snapshot(path)

    def test_tool_never_imports_or_calls_network_or_database_apis(self):
        source = Path(seed.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        roots, names, calls = set(), set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split('.')[0])
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Call):
                calls.add(node.func.id if isinstance(node.func, ast.Name) else
                          node.func.attr if isinstance(node.func, ast.Attribute) else '')
        allowed = {'argparse', 'hashlib', 'json', 'math', 'pathlib', 'struct', 'tokenizers', 'uuid'}
        forbidden = {'asyncio', 'ftplib', 'http', 'httpx', 'imaplib', 'poplib', 'psycopg', 'psycopg2',
                     'pymysql', 'requests', 'smtplib', 'socket', 'sqlite3', 'sqlalchemy', 'ssl',
                     'subprocess', 'supabase', 'supabase_auth', 'supabase_reader', 'telnetlib',
                     'urllib', 'webbrowser', 'xmlrpc'}
        forbidden_calls = {'connect', 'create_connection', 'cursor', 'execute', 'executemany',
                           'request', 'urlopen'}
        self.assertTrue(roots <= allowed, sorted(roots - allowed))
        self.assertFalse(forbidden & roots)
        self.assertFalse(forbidden & names)
        self.assertFalse(forbidden_calls & calls)


# Golden batch plan captured from the tool BEFORE the per-card split was added,
# with a pinned approval id (uuid4 -> '0' * 32). Regenerating the batch plan after
# the split must reproduce these exact bytes: the per-card mode may not alter the
# batch plan or the batch report in any way.
GOLDEN_BATCH_SQL_SHA = '560d145261740ccab393bca79415603e86973942d5ee0c4db9d958cc317df052'
GOLDEN_BATCH_REPORT_SHA = '2ad4c183ecf770e89b5de60819a92669ec95cfb55340ad1479611a5de4b73580'
PER_CARD_GUARD_LABELS = ('Card content guard failed', 'Expected no existing card embeddings',
                         'Card update count failed', 'Embedding count failed',
                         'Runtime readback failed', 'Vector wire guard failed')


class _FixedUUID:
    hex = '0' * 32


def stress_vector(text):
    """Worst-case serialization probe: four norm-carrying values plus many
    exponent-form float32 tails, so every component serializes long. Used only
    to measure an upper bound on per-card file size, never for plan content."""
    return [0.5] * 4 + [1e-20] * 380


class PerCardTests(unittest.TestCase):
    def test_batch_plan_is_byte_identical_to_the_pre_split_golden(self):
        data = snapshot_for(build_cards(12))
        with embed_patch(), patch.object(seed.uuid, 'uuid4', return_value=_FixedUUID):
            sql, report = seed.prepare(data)
        report_bytes = (json.dumps(report, ensure_ascii=True, indent=2) + '\n').encode('utf-8')
        self.assertEqual(hashlib.sha256(sql.encode('utf-8')).hexdigest(), GOLDEN_BATCH_SQL_SHA)
        self.assertEqual(hashlib.sha256(report_bytes).hexdigest(), GOLDEN_BATCH_REPORT_SHA)

    def test_per_card_emits_n_sql_files_plus_one_index(self):
        for count in (1, 2, 12):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'snapshot.json'
                data = snapshot_for(build_cards(count))
                snapshot.write_text(json.dumps(data), encoding='utf-8')
                with embed_patch(), patch('builtins.print'):
                    result = seed.main(['--snapshot', str(snapshot), '--output-dir', directory,
                                        '--per-card'])
                self.assertEqual(result, 0)
                sql_names = sorted(p.name for p in Path(directory).glob('card-seed-*.sql'))
                expected = sorted(seed.card_seed_name(c['card_id']) for c in data['cards'])
                self.assertEqual(sql_names, expected)
                self.assertEqual(len(sql_names), count)
                # Per-card mode never emits the batch artifacts.
                self.assertFalse((Path(directory) / seed.PLAN_NAME).exists())
                self.assertFalse((Path(directory) / seed.REPORT_NAME).exists())
                index = (Path(directory) / seed.PER_CARD_REPORT_NAME).read_text(encoding='utf-8')
                report = json.loads(index)
                self.assertEqual(report['count'], count)
                self.assertEqual(len(report['cards']), count)
                self.assertEqual(report['owner_id'], seed.OWNER)
                self.assertEqual(report['status'], 'manual_review_only')
                self.assertEqual(report['required_role'], seed.REQUIRED_ROLE)
                for card in data['cards']:
                    self.assertNotIn(card['positive_voice'], index)
                    self.assertNotIn(card['situation'], index)

    def test_each_per_card_file_is_self_contained_for_one_card(self):
        for count in (1, 2, 12):
            with self.subTest(count=count):
                cards = build_cards(count)
                data = snapshot_for(cards)
                with embed_patch():
                    plans, report = seed.prepare_per_card(seed.validate_snapshot(data))
                self.assertEqual(len(plans), count)
                for card, entry in zip(cards, report['cards'], strict=True):
                    name = seed.card_seed_name(card.card_id)
                    sql = dict(plans)[name]
                    self.assertEqual(entry['file'], name)
                    # Its own transaction envelope and its own table lock.
                    self.assertIn('BEGIN;', sql)
                    self.assertTrue(sql.endswith('COMMIT;\n'))
                    self.assertIn('LOCK TABLE public.editorial_cards, public.editorial_card_embeddings'
                                  ' IN SHARE ROW EXCLUSIVE MODE;', sql)
                    # All scoped guards present exactly once.
                    for label in PER_CARD_GUARD_LABELS:
                        self.assertEqual(sql.count(label), 1)
                    # The five scoped count guards, each scaled to 1, plus the
                    # no-existing-embedding EXISTS guard.
                    self.assertEqual(sql.count('<> 1'), 5)
                    self.assertIn('IF EXISTS (SELECT 1 FROM public.editorial_card_embeddings e', sql)
                    # Names exactly one card_id: no other card is referenced.
                    for other in cards:
                        self.assertEqual(other.card_id in sql, other.card_id == card.card_id)

    def test_per_card_fingerprints_and_wire_hashes_match_the_batch_report(self):
        for count in (1, 2, 12):
            with self.subTest(count=count):
                cards = build_cards(count)
                data = snapshot_for(cards)
                with embed_patch():
                    _, batch_report = seed.prepare(data)
                with embed_patch():
                    _, per_report = seed.prepare_per_card(seed.validate_snapshot(data))
                batch_by_id = {row['card_id']: row for row in batch_report['cards']}
                self.assertEqual({row['card_id'] for row in per_report['cards']}, set(batch_by_id))
                for row in per_report['cards']:
                    base = batch_by_id[row['card_id']]
                    self.assertEqual(row['fingerprint'], base['fingerprint'])
                    self.assertEqual(row['vector_wire_sha256'], base['vector_wire_sha256'])

    def test_guard_counts_scale_to_one_not_to_the_batch_count(self):
        for count in (2, 12):
            with self.subTest(count=count):
                cards = build_cards(count)
                with embed_patch():
                    plans, _ = seed.prepare_per_card(seed.validate_snapshot(snapshot_for(cards)))
                for _, sql in plans:
                    self.assertIn("IF affected <> 1 THEN RAISE EXCEPTION 'Card update count failed'", sql)
                    self.assertIn("IF affected <> 1 THEN RAISE EXCEPTION 'Embedding count failed'", sql)
                    self.assertRegex(sql, r"\) <> 1 THEN\s+RAISE EXCEPTION 'Card content guard failed'")
                    self.assertRegex(sql, r"\) <> 1 THEN\s+RAISE EXCEPTION 'Runtime readback failed'")
                    self.assertRegex(sql, r"\) <> 1 THEN\s+RAISE EXCEPTION 'Vector wire guard failed'")
                    self.assertEqual(sql.count('<> 1'), 5)
                    self.assertNotIn(f'<> {count}', sql)

    def test_per_card_outputs_are_never_overwritten(self):
        for count in (2, 12):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'snapshot.json'
                data = snapshot_for(build_cards(count))
                snapshot.write_text(json.dumps(data), encoding='utf-8')
                with embed_patch(), patch('builtins.print'):
                    self.assertEqual(seed.main(['--snapshot', str(snapshot), '--output-dir', directory,
                                                '--per-card']), 0)
                names = [seed.card_seed_name(c['card_id']) for c in data['cards']]
                names.append(seed.PER_CARD_REPORT_NAME)
                before = {name: (Path(directory) / name).read_bytes() for name in names}
                with embed_patch() as embed, patch('builtins.print'):
                    self.assertEqual(seed.main(['--snapshot', str(snapshot), '--output-dir', directory,
                                                '--per-card']), 1)
                embed.assert_not_called()
                for name in names:
                    self.assertEqual((Path(directory) / name).read_bytes(), before[name])

    def test_every_per_card_file_is_under_50000_bytes(self):
        worst = 0
        for count in (1, 2, 12):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'snapshot.json'
                snapshot.write_text(json.dumps(snapshot_for(build_cards(count))), encoding='utf-8')
                with patch.object(seed.local_embedding, 'embed_passages',
                                  side_effect=lambda texts: [stress_vector(text) for text in texts]), \
                        patch('builtins.print'):
                    self.assertEqual(seed.main(['--snapshot', str(snapshot), '--output-dir', directory,
                                                '--per-card']), 0)
                for path in Path(directory).glob('card-seed-*.sql'):
                    size = path.stat().st_size
                    worst = max(worst, size)
                    self.assertLess(size, 50000)
        self.assertGreater(worst, 0)


if __name__ == '__main__':
    unittest.main()
