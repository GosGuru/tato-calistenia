"""Offline tests: embedding is always mocked."""
import copy
import json
import struct
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from tools.editorial_rag import prepare_route_seed as seed


class SeedTests(unittest.TestCase):
    @patch.object(Path, 'read_text', side_effect=AssertionError('fixture must not read files'))
    def setUp(self, read_text):
        cards = [
            seed.Card(
                card_id=card_id, provenance_id='fictional_fixture',
                status='candidate', sanitized=True, phase='ruta',
                gate='fictional_gate', situation=f'Invented puzzle scenario {index}.',
                last_assistant_move='ask_puzzle', proposed_move='clarify_piece',
                positive_voice=f'Consider the imaginary blue piece {index}.',
                negative_repetition=f'Repeat the fictional puzzle clue {index}.',
            )
            for index, card_id in enumerate((
                'connect_help_to_concrete_gap', 'resolve_concrete_doubt_first',
            ))
        ]
        fingerprints = {card.card_id: seed.fingerprint(seed.OWNER, card) for card in cards}
        pins = patch.object(seed, 'FINGERPRINTS', fingerprints)
        pins.start()
        self.addCleanup(pins.stop)
        self.data = {
            'owner_id': seed.OWNER, 'fingerprints': dict(fingerprints),
            'cards': [dict(asdict(card), owner_id=seed.OWNER, approval_id=None) for card in cards],
        }
        read_text.assert_not_called()
        self.vector = [1.0] + [0.0] * 383

    def test_fixture_setup_without_file_reads(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('fixture must not read files')):
            cards = seed.validate_snapshot(self.data)
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(card.status == 'candidate' and card.sanitized for card in cards))

    def test_wire_sample(self):
        self.assertEqual(seed.vector_wire([1, 0, -0.5]).hex(), '000300003f80000000000000bf000000')

    def test_float32_roundtrip(self):
        for value in [0.0, -0.0, 1/3, 1e-38, -0.123456789, 1.17549435e-38]:
            self.assertEqual(struct.pack('>f', float(seed.vector_number(value))), struct.pack('>f', value))

    def test_exact_input_before_inference(self):
        cases = []
        for key, value in [('status', 'approved'), ('approval_id', 'old'), ('sanitized', False), ('owner_id', 'bad'), ('positive_voice', 'changed')]:
            data = copy.deepcopy(self.data)
            data['cards'][1][key] = value
            cases.append(data)
        data = copy.deepcopy(self.data)
        data['cards'][1] = data['cards'][0]
        cases.append(data)
        data = copy.deepcopy(self.data)
        data['extra'] = True
        cases.append(data)
        for data in cases:
            with self.subTest(data=list(data)), patch.object(seed.local_embedding, 'embed_passages') as embed:
                with self.assertRaises(seed.SeedError):
                    seed.prepare(data)
                embed.assert_not_called()

    def test_plan(self):
        with patch.object(seed.local_embedding, 'embed_passages', return_value=[self.vector, self.vector]) as embed:
            sql, report = seed.prepare(self.data)
        embed.assert_called_once()
        self.assertEqual(len(embed.call_args.args[0]), 2)
        self.assertEqual(report['count'], 2)
        self.assertIn('GET DIAGNOSTICS affected = ROW_COUNT', sql)
        self.assertIn('extensions.vector_send', sql)
        self.assertIn('public.editorial_runtime_library', sql)
        self.assertNotIn('ON CONFLICT', sql)
        self.assertNotIn(self.data['cards'][0]['positive_voice'], sql)
        self.assertTrue(sql.endswith('COMMIT;\n'))

    def test_failure_no_retry(self):
        with patch.object(seed.local_embedding, 'embed_passages', side_effect=seed.local_embedding.EmbeddingError('embedding_unavailable')) as embed, self.assertRaisesRegex(seed.SeedError, '^embedding_failed$'):
            seed.prepare(self.data)
        embed.assert_called_once()

    def test_invalid_vectors(self):
        for vector in [[0.0]*384, [float('nan')]*384, [1.0]]:
            with patch.object(seed.local_embedding, 'embed_passages', return_value=[vector, vector]), self.assertRaises(seed.SeedError):
                seed.prepare(self.data)

    def test_existing_output_prevents_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)/'snapshot.json'
            snapshot.write_text(json.dumps(self.data), encoding='utf-8')
            path = Path(directory)/'route-seed-plan.sql'
            path.write_text('keep', encoding='utf-8')
            with patch.object(seed.local_embedding, 'embed_passages') as embed, patch('builtins.print'):
                result = seed.main(['--snapshot', str(snapshot), '--output-dir', directory])
            self.assertEqual(result, 1)
            self.assertEqual(path.read_text(encoding='utf-8'), 'keep')
            embed.assert_not_called()

    def test_cli_writes_fictional_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)/'snapshot.json'
            snapshot.write_text(json.dumps(self.data), encoding='utf-8')
            with patch.object(seed.local_embedding, 'embed_passages', return_value=[self.vector, self.vector]) as embed, patch('builtins.print'):
                result = seed.main(['--snapshot', str(snapshot), '--output-dir', directory])
            self.assertEqual(result, 0)
            embed.assert_called_once()
            self.assertEqual(len(embed.call_args.args[0]), 2)
            sql = (Path(directory)/'route-seed-plan.sql').read_text(encoding='utf-8')
            report = json.loads((Path(directory)/'route-seed-report.json').read_text(encoding='utf-8'))
            self.assertTrue(sql.endswith('COMMIT;\n'))
            self.assertEqual(report['count'], 2)
            self.assertEqual(report['status'], 'manual_review_only')
            self.assertEqual({row['card_id']: row['fingerprint'] for row in report['cards']}, self.data['fingerprints'])
            for card in self.data['cards']:
                self.assertNotIn(card['positive_voice'], sql)

    def test_strict_bounded_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'snapshot.json'
            for raw in ['{"owner_id":1,"owner_id":2}', '{"x":NaN}', ' '*65537]:
                path.write_text(raw, encoding='utf-8')
                with self.assertRaises(seed.SeedError):
                    seed.load_snapshot(path)

if __name__ == '__main__':
    unittest.main()
