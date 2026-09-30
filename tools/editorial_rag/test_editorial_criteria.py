import hashlib
import json
import unittest
from dataclasses import asdict, replace
from pathlib import Path

if __package__:
    from .editorial_criteria import (
        CONTENT_FIELDS,
        MODEL_METADATA,
        criterion_passage,
        fingerprint,
        parse_criterion,
    )
    from .prototype import Card
else:
    from editorial_criteria import (
        CONTENT_FIELDS,
        MODEL_METADATA,
        criterion_passage,
        fingerprint,
        parse_criterion,
    )
    from prototype import Card

OWNER = '11111111-1111-4111-8111-111111111111'
CARD = Card('fictional', 'synthetic', 'candidate', True, 'ruta', 'pending', 'condición | á🙂', 'clarify', 'explain', 'criterio positivo', 'no adelantar llamada')
VECTOR = [1.0] + [0.0]*383

def row():
    return {**asdict(replace(CARD, status='approved')), 'owner_id': OWNER, 'approval_id': 'approval-fictional', 'fingerprint': fingerprint(OWNER, CARD), **MODEL_METADATA, 'embedding': json.dumps(VECTOR)}

class CriteriaTests(unittest.TestCase):
    def test_framing_and_candidate_passage(self):
        values = [OWNER] + [('true' if getattr(CARD, name) else 'false') if name == 'sanitized' else getattr(CARD, name) for name in CONTENT_FIELDS[1:]]
        framed = b''.join(str(len(v.encode('utf-8'))).encode()+b':'+v.encode('utf-8') for v in values)
        self.assertEqual(fingerprint(OWNER, CARD), hashlib.sha256(framed).hexdigest())
        self.assertEqual(fingerprint(OWNER, CARD), fingerprint(OWNER, replace(CARD, status='approved')))
        self.assertNotEqual(fingerprint(OWNER, replace(CARD, situation='a|b', positive_voice='c')), fingerprint(OWNER, replace(CARD, situation='a', positive_voice='b|c')))
        self.assertIn(CARD.negative_repetition, criterion_passage(CARD))
        self.assertIn(CARD.gate, criterion_passage(CARD))
        self.assertFalse(criterion_passage(CARD).startswith('passage:'))
        self.assertNotEqual(fingerprint(OWNER, replace(CARD, situation='é')), fingerprint(OWNER, replace(CARD, situation='e\u0301')))
        with self.assertRaises(ValueError):
            fingerprint(OWNER, replace(CARD, situation='bad\x00text'))
        with self.assertRaises(ValueError):
            fingerprint(OWNER, replace(CARD, situation='bad\ud800text'))

    def test_integrity_fail_closed(self):
        self.assertEqual(parse_criterion(row(), OWNER).embedding.vector, tuple(VECTOR))
        for patch in [{'status':'candidate'}, {'sanitized':False}, {'fingerprint':'0'*64}, {'approval_id':None}, {'owner_id':'22222222-2222-4222-8222-222222222222'}, {'dimensions':True}, {'revision':'wrong'}, {'embedding':'[NaN]'}, {'embedding':json.dumps([0]*384)}, {'embedding':json.dumps([True]+[0]*383)}, {'situation':'x'*2001}, {'extra':1}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                parse_criterion({**row(), **patch}, OWNER)

    def test_sql_static_contract(self):
        sql = Path(__file__).with_name('002_editorial_embeddings.sql').read_text(encoding='utf-8').lower()
        for fragment in ['security_invoker = true', 'force row level security', 'extensions.vector(384)', 'pg_catalog.sha256', 'octet_length', 'c.approval_id = e.approval_id', 'c.status = \'approved\'', 'revoke all', 'for select to authenticated']:
            self.assertIn(fragment, sql)
        self.assertNotIn('security definer', sql)
        self.assertNotIn('alter table public.editorial_cards', sql)
