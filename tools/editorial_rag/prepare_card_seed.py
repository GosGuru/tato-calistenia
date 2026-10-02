"""Bounded offline plan only. Never executes SQL or authorizes activation.

General N-card sibling of prepare_route_seed.py (1..50 candidate cards per plan).
That tool serves one frozen historical batch with pinned fingerprints; this one
derives every fingerprint from the snapshot content and guards an arbitrary batch.
It reads local data and writes one plan plus one report; it never connects to a
database or a network service and never authorizes activation.
"""
import argparse
import hashlib
import json
import math
import struct
import uuid
from pathlib import Path

from tokenizers import Tokenizer

from . import local_embedding
from .editorial_criteria import (
    CARD_FIELDS,
    MODEL_METADATA,
    criterion_passage,
    fingerprint,
    validate_vector,
)
from .model_setup import CACHE, SPEC
from .prototype import Card

OWNER = '3ff38843-a271-4df9-81e5-285179227bd0'
MIN_CARDS = 1
MAX_CARDS = 50
# Bounded parse sized for MAX_CARDS rows at the 2,000-character field ceiling,
# the fingerprint map and the JSON envelope. Deliberately not unbounded.
MAX_SNAPSHOT_BYTES = 524288
# Real embedder ceiling and prefix from the pinned model manifest; the tokenizer
# is the pinned tokenizer.json of the same cache the embedder loads.
PASSAGE_PREFIX = SPEC['passage_prefix']
PASSAGE_TOKEN_CEILING = SPEC['max_tokens']
MAX_EMBED_BATCH = SPEC['max_passages']
PLAN_NAME = 'card-seed-plan.sql'
REPORT_NAME = 'card-seed-report.json'
# Per-card mode splits the batch into one self-guarded plan per card plus one index.
PER_CARD_REPORT_NAME = 'card-seed-per-card-report.json'
PER_CARD_PREFIX = 'card-seed-'
PER_CARD_SUFFIX = '.sql'
REQUIRED_ROLE = 'postgres or service_role (role with BYPASSRLS)'
_TOKENIZER = None


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
            data = stream.read(MAX_SNAPSHOT_BYTES + 1)
        if len(data) > MAX_SNAPSHOT_BYTES:
            raise ValueError
        return json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise SeedError('invalid_snapshot') from None


def validate_snapshot(data):
    """Exact schema, owner pin, claimed count agreement and derived fingerprints.

    The snapshot claims its card count and its fingerprints; both must agree with
    the cards it actually contains. Fingerprints are recomputed from content with
    editorial_criteria.fingerprint and never trusted or pinned here.
    """
    try:
        if type(data) is not dict or set(data) != {'owner_id', 'count', 'fingerprints', 'cards'}:
            raise ValueError
        if data['owner_id'] != OWNER:
            raise ValueError
        claimed = data['fingerprints']
        rows = data['cards']
        if type(claimed) is not dict or type(rows) is not list:
            raise ValueError
        claimed_count = data['count']
        if type(claimed_count) is not int or not MIN_CARDS <= claimed_count <= MAX_CARDS:
            raise ValueError
        # Count guards: the snapshot may not claim a different number of cards
        # than it contains, in either direction.
        if claimed_count != len(rows) or len(claimed) != len(rows):
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
            if fingerprint(OWNER, card) != claimed.get(card.card_id):
                raise ValueError
            cards[card.card_id] = card
        if set(cards) != set(claimed):
            raise ValueError
        return [cards[row['card_id']] for row in rows]
    except Exception:
        raise SeedError('invalid_snapshot') from None


def _tokenizer():
    """Pinned tokenizer.json of the real embedder. No model, no network."""
    global _TOKENIZER
    if _TOKENIZER is None:
        try:
            _TOKENIZER = Tokenizer.from_file(str(CACHE / 'tokenizer.json'))
        except Exception:
            raise SeedError('tokenizer_unavailable') from None
    return _TOKENIZER


def passage_tokens(text):
    """Real embedder token count of passage_prefix + text, special tokens included.

    Same input, tokenizer file and add_special_tokens convention as the
    tokenLength the embedder enforces in embedding_node/embed.mjs.
    """
    try:
        return len(_tokenizer().encode(PASSAGE_PREFIX + text, add_special_tokens=True).ids)
    except SeedError:
        raise
    except Exception:
        raise SeedError('tokenizer_unavailable') from None


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


def _embed_batches(passages):
    try:
        return [local_embedding.embed_passages(passages[start:start + MAX_EMBED_BATCH])
                for start in range(0, len(passages), MAX_EMBED_BATCH)]
    except Exception:
        raise SeedError('embedding_failed') from None


def card_seed_name(card_id):
    """One plan file per card: `card-seed-<card_id>.sql`."""
    return PER_CARD_PREFIX + str(card_id) + PER_CARD_SUFFIX


def _embed_facts(cards):
    """Validate, embed and fingerprint one validated card list.

    Shared by the batch plan and the per-card plans so the split is faithful:
    returns (vectors, fingerprints, hashes) derived only from this batch's
    content. The real embedder token ceiling is checked per card before any
    inference.
    """
    passages = [criterion_passage(card) for card in cards]
    # Real token ceiling of the embedder, checked per card before any inference.
    if any(passage_tokens(text) > PASSAGE_TOKEN_CEILING for text in passages):
        raise SeedError('passage_too_long')
    batches = _embed_batches(passages)
    try:
        vectors = [vector for batch in batches for vector in batch]
        if type(vectors) is not list or len(vectors) != len(cards):
            raise ValueError
        vectors = [validate_vector(vector) for vector in vectors]
        # Validate the actual float32 representation PostgreSQL will store too.
        vectors = [validate_vector(tuple(struct.unpack('>f', struct.pack('>f', x))[0] for x in vector)) for vector in vectors]
    except Exception:
        raise SeedError('invalid_vectors') from None
    # Derived from this batch's content; nothing is pinned per card.
    fingerprints = [fingerprint(OWNER, card) for card in cards]
    hashes = [hashlib.sha256(vector_wire(vector)).hexdigest() for vector in vectors]
    return vectors, fingerprints, hashes


def prepare(data):
    cards = validate_snapshot(data)
    vectors, fingerprints, hashes = _embed_facts(cards)
    count = len(cards)
    approval = 'rag-card-' + uuid.uuid4().hex
    expected = ', '.join('(' + ', '.join(map(_literal, (card.card_id, fp, wirehash))) + ')'
                         for card, fp, wirehash in zip(cards, fingerprints, hashes, strict=True))
    ids = ', '.join(map(_literal, (card.card_id for card in cards)))
    # One content guard per card: each card's current fingerprint is verified in
    # the database before approving, and the transaction aborts on any mismatch.
    guards = '\n    '.join(
        f"""IF (SELECT count(*) FROM public.editorial_cards c
        WHERE c.owner_id = '{OWNER}' AND c.card_id = {_literal(card.card_id)}
          AND c.status = 'candidate' AND c.approval_id IS NULL
          AND c.sanitized AND public.editorial_content_fingerprint(c) = {_literal(fp)}) <> 1 THEN
        RAISE EXCEPTION 'Card content guard failed';
    END IF;"""  # noqa: S608 -- offline SQL artifact; escaped literals only
        for card, fp in zip(cards, fingerprints, strict=True))
    columns = ['owner_id', 'card_id', 'approval_id', 'fingerprint', *MODEL_METADATA, 'embedding']
    dimensions = MODEL_METADATA['dimensions']
    inserts = []
    for card, vector, fp in zip(cards, vectors, fingerprints, strict=True):
        values = [OWNER, card.card_id, approval, fp, *MODEL_METADATA.values()]
        serialized = '[' + ','.join(map(vector_number, vector)) + ']'
        inserts.append('(' + ', '.join(map(_literal, values)) + ', ' + _literal(serialized)
                       + f'::extensions.vector({dimensions}))')
    metadata = ' AND '.join('r.' + name + ' = ' + _literal(value) for name, value in MODEL_METADATA.items())
    # All interpolated values are pinned constants, generated UUID hex, or escaped literals.
    sql = f"""-- Manual review only; this plan is not authorization. No source prose.
BEGIN;
DO $card_seed$
DECLARE affected integer;
BEGIN
    LOCK TABLE public.editorial_cards, public.editorial_card_embeddings IN SHARE ROW EXCLUSIVE MODE;
    {guards}
    IF EXISTS (SELECT 1 FROM public.editorial_card_embeddings e
        WHERE e.owner_id = '{OWNER}' AND e.card_id IN ({ids})) THEN
        RAISE EXCEPTION 'Expected no existing card embeddings';
    END IF;
    UPDATE public.editorial_cards SET status = 'approved', approval_id = '{approval}'
        WHERE owner_id = '{OWNER}' AND card_id IN ({ids})
          AND status = 'candidate' AND approval_id IS NULL;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> {count} THEN RAISE EXCEPTION 'Card update count failed'; END IF;
    INSERT INTO public.editorial_card_embeddings ({', '.join(columns)}) VALUES
        {', '.join(inserts)};
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> {count} THEN RAISE EXCEPTION 'Embedding count failed'; END IF;
    IF (SELECT count(*) FROM public.editorial_runtime_library
        WHERE owner_id = '{OWNER}' AND approval_id = '{approval}') <> {count}
       OR (SELECT count(*) FROM public.editorial_runtime_library r
           JOIN (VALUES {expected}) AS x(card_id, fingerprint, wirehash) ON x.card_id = r.card_id
           WHERE r.owner_id = '{OWNER}' AND r.approval_id = '{approval}' AND r.fingerprint = x.fingerprint
             AND pg_catalog.encode(pg_catalog.sha256(extensions.vector_send(r.embedding::extensions.vector)), 'hex') = x.wirehash
             AND {metadata}) <> {count} THEN
        RAISE EXCEPTION 'Runtime readback failed';
    END IF;
    IF (SELECT count(*) FROM public.editorial_card_embeddings e
        JOIN (VALUES {expected}) AS x(card_id, fingerprint, wirehash) ON x.card_id = e.card_id
        WHERE e.owner_id = '{OWNER}' AND e.approval_id = '{approval}' AND e.fingerprint = x.fingerprint
          AND pg_catalog.encode(pg_catalog.sha256(extensions.vector_send(e.embedding)), 'hex') = x.wirehash) <> {count} THEN
        RAISE EXCEPTION 'Vector wire guard failed';
    END IF;
END $card_seed$;
COMMIT;
"""  # noqa: S608 -- offline SQL artifact; constants and escaped literals only
    report = {'count': count, 'dimensions': MODEL_METADATA['dimensions'], 'approval_id': approval,
              'model_metadata': dict(MODEL_METADATA),
              'cards': [{'card_id': card.card_id, 'fingerprint': fp,
                         'vector_wire_sha256': wirehash,
                         'norm': math.sqrt(math.fsum(x*x for x in vector))}
                        for card, fp, vector, wirehash in zip(cards, fingerprints, vectors, hashes, strict=True)],
              'sql_sha256': hashlib.sha256(sql.encode('utf-8')).hexdigest(),
              'status': 'manual_review_only'}
    return sql, report


def _card_sql(card, vector, fp, wirehash, approval):
    """One self-contained, atomic plan for exactly one card.

    Same header, lock and guard style as the batch plan, scoped to a single
    card and scaled to count 1. Every interpolated literal is escaped by
    `_literal`; nothing here is network or database related.
    """
    columns = ['owner_id', 'card_id', 'approval_id', 'fingerprint', *MODEL_METADATA, 'embedding']
    dimensions = MODEL_METADATA['dimensions']
    values = [OWNER, card.card_id, approval, fp, *MODEL_METADATA.values()]
    serialized = '[' + ','.join(map(vector_number, vector)) + ']'
    insert = '(' + ', '.join(map(_literal, values)) + ', ' + _literal(serialized)
    insert += f'::extensions.vector({dimensions}))'
    metadata = ' AND '.join('r.' + name + ' = ' + _literal(value) for name, value in MODEL_METADATA.items())
    cid = _literal(card.card_id)
    sql = f"""-- Manual review only; this plan is not authorization. No source prose.
-- Required role: {REQUIRED_ROLE}, used in the Supabase SQL editor.
-- FORCE ROW LEVEL SECURITY and the TO authenticated insert policy deny any other role,
-- and a run without a JWT makes auth.uid() NULL and fails the policy check.
-- Approval reference: {approval} (one approval event shared by every per-card plan of this batch).
BEGIN;
DO $card_seed$
DECLARE affected integer;
BEGIN
    LOCK TABLE public.editorial_cards, public.editorial_card_embeddings IN SHARE ROW EXCLUSIVE MODE;
    IF (SELECT count(*) FROM public.editorial_cards c
        WHERE c.owner_id = '{OWNER}' AND c.card_id = {cid}
          AND c.status = 'candidate' AND c.approval_id IS NULL
          AND c.sanitized AND public.editorial_content_fingerprint(c) = {_literal(fp)}) <> 1 THEN
        RAISE EXCEPTION 'Card content guard failed';
    END IF;
    IF EXISTS (SELECT 1 FROM public.editorial_card_embeddings e
        WHERE e.owner_id = '{OWNER}' AND e.card_id = {cid}) THEN
        RAISE EXCEPTION 'Expected no existing card embeddings';
    END IF;
    UPDATE public.editorial_cards SET status = 'approved', approval_id = '{approval}'
        WHERE owner_id = '{OWNER}' AND card_id = {cid}
          AND status = 'candidate' AND approval_id IS NULL;
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN RAISE EXCEPTION 'Card update count failed'; END IF;
    INSERT INTO public.editorial_card_embeddings ({', '.join(columns)}) VALUES
        {insert};
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> 1 THEN RAISE EXCEPTION 'Embedding count failed'; END IF;
    IF (SELECT count(*) FROM public.editorial_runtime_library r
        WHERE r.owner_id = '{OWNER}' AND r.card_id = {cid} AND r.approval_id = '{approval}'
          AND r.fingerprint = {_literal(fp)} AND {metadata}) <> 1 THEN
        RAISE EXCEPTION 'Runtime readback failed';
    END IF;
    IF (SELECT count(*) FROM public.editorial_card_embeddings e
        WHERE e.owner_id = '{OWNER}' AND e.card_id = {cid} AND e.approval_id = '{approval}'
          AND pg_catalog.encode(pg_catalog.sha256(extensions.vector_send(e.embedding)), 'hex') = {_literal(wirehash)}) <> 1 THEN
        RAISE EXCEPTION 'Vector wire guard failed';
    END IF;
END $card_seed$;
COMMIT;
"""  # noqa: S608 -- offline SQL artifact; constants and escaped literals only
    return sql


def prepare_per_card(cards):
    """One self-guarded plan per card plus one index report.

    `cards` is a validated card list (from `validate_snapshot`). A single
    approval id is shared by every per-card plan because the batch is one
    approval event. Returns (plans, report) where plans is a list of
    (filename, sql) pairs in card order.
    """
    vectors, fingerprints, hashes = _embed_facts(cards)
    count = len(cards)
    approval = 'rag-card-' + uuid.uuid4().hex
    plans = []
    entries = []
    for card, vector, fp, wirehash in zip(cards, vectors, fingerprints, hashes, strict=True):
        sql = _card_sql(card, vector, fp, wirehash, approval)
        name = card_seed_name(card.card_id)
        plans.append((name, sql))
        entries.append({'card_id': card.card_id, 'fingerprint': fp,
                        'vector_wire_sha256': wirehash,
                        'sql_sha256': hashlib.sha256(sql.encode('utf-8')).hexdigest(),
                        'file': name})
    report = {'count': count, 'owner_id': OWNER, 'approval_id': approval,
              'cards': entries, 'status': 'manual_review_only',
              'required_role': REQUIRED_ROLE}
    return plans, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--per-card', action='store_true',
                        help='emit one self-guarded plan per card plus one index report')
    args = parser.parse_args(argv)
    try:
        directory = Path(args.output_dir)
        if args.per_card:
            data = load_snapshot(args.snapshot)
            cards = validate_snapshot(data)
            paths = [directory / card_seed_name(card.card_id) for card in cards]
            paths.append(directory / PER_CARD_REPORT_NAME)
            if any(path.exists() for path in paths):
                raise SeedError('output_exists')
            plans, report = prepare_per_card(cards)
            payloads = [sql.encode('utf-8') for _, sql in plans]
            payloads.append((json.dumps(report, ensure_ascii=True, indent=2) + '\n').encode('utf-8'))
        else:
            paths = [directory / PLAN_NAME, directory / REPORT_NAME]
            if any(path.exists() for path in paths):
                raise SeedError('output_exists')
            sql, report = prepare(load_snapshot(args.snapshot))
            payloads = [sql.encode('utf-8'), (json.dumps(report, ensure_ascii=True, indent=2) + '\n').encode('utf-8')]
        # Exclusive creation: never overwrite. A write failure may leave a partial artifact.
        for path, payload in zip(paths, payloads, strict=True):
            with path.open('xb') as stream:
                stream.write(payload)
        print(json.dumps({'outputs': [{'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest()}
                                     for path, payload in zip(paths, payloads, strict=True)],
                          'count': report['count']}))
        return 0
    except SeedError as error:
        print(str(error))
        return 1
    except Exception:
        print('seed_plan_failed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
