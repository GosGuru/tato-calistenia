"""Bounded offline plan only. Never executes SQL or authorizes activation."""
import argparse
import hashlib
import json
import math
import struct
import uuid
from pathlib import Path

from . import local_embedding
from .editorial_criteria import (
    CARD_FIELDS,
    MODEL_METADATA,
    criterion_passage,
    fingerprint,
    validate_vector,
)
from .prototype import Card

OWNER = '3ff38843-a271-4df9-81e5-285179227bd0'
FINGERPRINTS = {
    'connect_help_to_concrete_gap': 'e49db20d9a4d91e60f81eeec3209f822f5d2991220198adcd2ea45f63414cb18',
    'resolve_concrete_doubt_first': 'ce2cc39d67a7684ed13d9ed8eae59dc171f3cc52f0c6bc19457633e61b0f93d0',
}
OTHER_IDS = ('separate_observation_from_inference', 'ask_only_missing_evidence', 'respond_without_pressure')

class SeedError(RuntimeError):
    """Fixed, content-free public errors."""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SeedError('invalid_snapshot')
        result[key] = value
    return result


def load_snapshot(path):
    try:
        with Path(path).open('rb') as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError
        return json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise SeedError('invalid_snapshot') from None


def validate_snapshot(data):
    try:
        if type(data) is not dict or set(data) != {'owner_id', 'fingerprints', 'cards'}:
            raise ValueError
        if data['owner_id'] != OWNER or data['fingerprints'] != FINGERPRINTS:
            raise ValueError
        rows = data['cards']
        if type(rows) is not list or len(rows) != 2:
            raise ValueError
        cards = {}
        for row in rows:
            if type(row) is not dict or set(row) != set(CARD_FIELDS) | {'owner_id', 'approval_id'}:
                raise ValueError
            if row['owner_id'] != OWNER or row['approval_id'] is not None:
                raise ValueError
            card = Card(**{key: row[key] for key in CARD_FIELDS})
            if card.status != 'candidate' or (type(card.sanitized) is not bool or not card.sanitized) or card.card_id in cards:
                raise ValueError
            if fingerprint(OWNER, card) != FINGERPRINTS.get(card.card_id):
                raise ValueError
            cards[card.card_id] = card
        if set(cards) != set(FINGERPRINTS):
            raise ValueError
        return [cards[key] for key in FINGERPRINTS]
    except Exception:
        raise SeedError('invalid_snapshot') from None


def vector_wire(vector):
    return struct.pack('>hh', len(vector), 0) + b''.join(struct.pack('>f', value) for value in vector)


def vector_number(value):
    original = struct.pack('>f', value)
    number = struct.unpack('>f', original)[0]
    short = format(number, '.9g')
    try:
        return short if struct.pack('>f', float(short)) == original else repr(number)
    except (ValueError, OverflowError):
        return repr(number)


def _literal(value):
    if type(value) is int:
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def prepare(data):
    cards = validate_snapshot(data)
    passages = [criterion_passage(card) for card in cards]
    try:
        vectors = local_embedding.embed_passages(passages)
    except Exception:
        raise SeedError('embedding_failed') from None
    try:
        if type(vectors) is not list or len(vectors) != 2:
            raise ValueError
        vectors = [validate_vector(vector) for vector in vectors]
        # Validate the actual float32 representation PostgreSQL will store too.
        vectors = [validate_vector(tuple(struct.unpack('>f', struct.pack('>f', x))[0] for x in vector)) for vector in vectors]
    except Exception:
        raise SeedError('invalid_vectors') from None
    approval = 'rag-route-' + uuid.uuid4().hex
    hashes = [hashlib.sha256(vector_wire(vector)).hexdigest() for vector in vectors]
    expected = ', '.join('(' + ', '.join(map(_literal, (card.card_id, FINGERPRINTS[card.card_id], wirehash))) + ')'
                         for card, wirehash in zip(cards, hashes, strict=True))
    ids = ', '.join(map(_literal, FINGERPRINTS))
    other = ', '.join(map(_literal, OTHER_IDS))
    columns = ['owner_id', 'card_id', 'approval_id', 'fingerprint', *MODEL_METADATA, 'embedding']
    inserts = []
    for card, vector in zip(cards, vectors, strict=True):
        values = [OWNER, card.card_id, approval, FINGERPRINTS[card.card_id], *MODEL_METADATA.values()]
        serialized = '[' + ','.join(map(vector_number, vector)) + ']'
        inserts.append('(' + ', '.join(map(_literal, values)) + ', ' + _literal(serialized) + '::extensions.vector(384))')
    # All interpolated values are pinned constants, generated UUID hex, or escaped literals.
    sql = f"""-- Manual review only; this plan is not authorization. No source prose.
BEGIN;
DO $route_seed$
DECLARE affected integer;
BEGIN
    LOCK TABLE public.editorial_cards, public.editorial_card_embeddings IN SHARE ROW EXCLUSIVE MODE;
    IF (SELECT count(*) FROM public.editorial_cards c
        WHERE c.owner_id = '{OWNER}' AND c.card_id IN ({other})
          AND c.status = 'candidate' AND c.approval_id IS NULL) <> 3 THEN
        RAISE EXCEPTION 'Other candidate guard failed';
    END IF;
    IF (SELECT count(*) FROM public.editorial_cards c
        JOIN (VALUES {expected}) AS x(card_id, fingerprint, wirehash) ON x.card_id = c.card_id
        WHERE c.owner_id = '{OWNER}' AND c.status = 'candidate' AND c.approval_id IS NULL
          AND c.sanitized AND public.editorial_content_fingerprint(c) = x.fingerprint) <> 2 THEN
        RAISE EXCEPTION 'Route content guard failed';
    END IF;
    IF EXISTS (SELECT 1 FROM public.editorial_card_embeddings WHERE owner_id = '{OWNER}') THEN
        RAISE EXCEPTION 'Expected empty owner embeddings';
    END IF;
    UPDATE public.editorial_cards SET status = 'approved', approval_id = '{approval}'
        WHERE owner_id = '{OWNER}' AND card_id IN ({ids})
          AND status = 'candidate' AND approval_id IS NULL;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 2 THEN RAISE EXCEPTION 'Route update count failed'; END IF;
    INSERT INTO public.editorial_card_embeddings ({', '.join(columns)}) VALUES
        {', '.join(inserts)};
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 2 THEN RAISE EXCEPTION 'Embedding count failed'; END IF;
    IF (SELECT count(*) FROM public.editorial_runtime_library WHERE owner_id = '{OWNER}') <> 2
       OR (SELECT count(*) FROM public.editorial_runtime_library r
           JOIN (VALUES {expected}) AS x(card_id, fingerprint, wirehash) ON r.card_id = x.card_id
           WHERE r.owner_id = '{OWNER}' AND r.approval_id = '{approval}' AND r.fingerprint = x.fingerprint
             AND pg_catalog.encode(pg_catalog.sha256(extensions.vector_send(r.embedding::extensions.vector)), 'hex') = x.wirehash
             AND {' AND '.join('r.' + name + ' = ' + _literal(value) for name, value in MODEL_METADATA.items())}) <> 2 THEN
        RAISE EXCEPTION 'Runtime readback failed';
    END IF;
    IF (SELECT count(*) FROM public.editorial_card_embeddings e
        JOIN (VALUES {expected}) AS x(card_id, fingerprint, wirehash) ON e.card_id = x.card_id
        WHERE e.owner_id = '{OWNER}' AND e.approval_id = '{approval}' AND e.fingerprint = x.fingerprint
          AND pg_catalog.encode(pg_catalog.sha256(extensions.vector_send(e.embedding)), 'hex') = x.wirehash) <> 2 THEN
        RAISE EXCEPTION 'Vector wire guard failed';
    END IF;
END $route_seed$;
COMMIT;
"""  # noqa: S608 -- offline SQL artifact; constants and escaped literals only
    report = {'count': 2, 'dimensions': 384, 'approval_id': approval, 'model_metadata': dict(MODEL_METADATA),
              'cards': [{'card_id': card.card_id, 'fingerprint': FINGERPRINTS[card.card_id],
                         'vector_wire_sha256': wirehash, 'norm': math.sqrt(math.fsum(x*x for x in vector))}
                        for card, vector, wirehash in zip(cards, vectors, hashes, strict=True)],
              'sql_sha256': hashlib.sha256(sql.encode('utf-8')).hexdigest(), 'status': 'manual_review_only'}
    return sql, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        directory = Path(args.output_dir)
        paths = [directory / 'route-seed-plan.sql', directory / 'route-seed-report.json']
        if any(path.exists() for path in paths):
            raise SeedError('output_exists')
        sql, report = prepare(load_snapshot(args.snapshot))
        encoded = [sql.encode('utf-8'), (json.dumps(report, ensure_ascii=True, indent=2) + '\n').encode('utf-8')]
        # Exclusive creation: never overwrite. A write failure may leave a partial artifact.
        for path, payload in zip(paths, encoded, strict=True):
            with path.open('xb') as stream:
                stream.write(payload)
        print(json.dumps({'outputs': [{'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest()}
                                     for path, payload in zip(paths, encoded, strict=True)], 'count': 2}))
        return 0
    except SeedError as error:
        print(str(error))
        return 1
    except Exception:
        print('seed_plan_failed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
