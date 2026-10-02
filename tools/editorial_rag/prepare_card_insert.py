"""Bounded offline plan only. Never executes SQL or authorizes activation.

Candidate-row sibling of prepare_card_seed.py: this tool emits the INSERT that
creates `candidate` rows in public.editorial_cards, so the already-reviewed seed
plan can later approve those same rows and embed them. The snapshot contract is
imported from prepare_card_seed, never re-implemented here. It reads local data
and writes one plan plus one report; it never connects to a database or a
network service and never authorizes activation.

The generated INSERT deliberately omits `status` and `approval_id`: the insert
grant is column-scoped without them, the table defaults ('candidate', NULL)
satisfy the RLS insert policy, and those two columns must never be written by
this plan.
"""
import argparse
import hashlib
import json
import uuid
from pathlib import Path

# Single source of truth: the fingerprint from editorial_criteria, and the snapshot
# schema, the owner pin and the literal escaping discipline from prepare_card_seed.
# Nothing here re-validates or re-escapes by hand.
from .editorial_criteria import fingerprint
from .prepare_card_seed import (
    OWNER,
    SeedError,
    _literal,
    load_snapshot,
    validate_snapshot,
)

# The eleven columns of the column-scoped insert grant on public.editorial_cards.
# `status` and `approval_id` are deliberately absent: their column defaults apply.
GRANTED_COLUMNS = ('owner_id', 'card_id', 'provenance_id', 'sanitized', 'phase', 'gate',
                   'situation', 'last_assistant_move', 'proposed_move', 'positive_voice',
                   'negative_repetition')
REQUIRED_ROLE = 'postgres or service_role (role with BYPASSRLS)'
PLAN_NAME = 'card-insert-plan.sql'
REPORT_NAME = 'card-insert-report.json'


def _insert_row(card):
    """One VALUES tuple, in GRANTED_COLUMNS order, every literal escaped."""
    # validate_snapshot guarantees sanitized is exactly True, so the bare TRUE is
    # a pinned constant, never interpolated card content.
    parts = [_literal(OWNER), _literal(card.card_id), _literal(card.provenance_id), 'TRUE',
             _literal(card.phase), _literal(card.gate), _literal(card.situation),
             _literal(card.last_assistant_move), _literal(card.proposed_move),
             _literal(card.positive_voice), _literal(card.negative_repetition)]
    return '(' + ', '.join(parts) + ')'


def prepare(data):
    """Candidate INSERT plan plus report from a validated snapshot.

    Fingerprints are the same derived values the seed plan's content guards will
    verify in the database before approving, so this plan must reproduce them
    exactly or the seed plan aborts.
    """
    cards = validate_snapshot(data)
    # Derived from this batch's content through the shared contract; nothing pinned.
    fingerprints = [fingerprint(OWNER, card) for card in cards]
    count = len(cards)
    approval = 'rag-card-insert-' + uuid.uuid4().hex
    ids = ', '.join(_literal(card.card_id) for card in cards)
    expected = ', '.join('(' + ', '.join(_literal(value) for value in pair) + ')'
                         for pair in ((card.card_id, fp) for card, fp in zip(cards, fingerprints, strict=True)))
    inserts = ', '.join(_insert_row(card) for card in cards)
    sql = f"""-- Manual review only; this plan is not authorization. No database or network call.
-- Required role: {REQUIRED_ROLE}, used in the Supabase SQL editor.
-- FORCE ROW LEVEL SECURITY and the TO authenticated insert policy deny any other role,
-- and a run without a JWT makes auth.uid() NULL and fails the policy check.
-- Approval reference: {approval} (plan identifier only; the rows keep the column defaults).
BEGIN;
DO $card_insert$
DECLARE affected integer;
BEGIN
    LOCK TABLE public.editorial_cards IN SHARE ROW EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM public.editorial_cards c
        WHERE c.owner_id = '{OWNER}' AND c.card_id IN ({ids})) THEN
        RAISE EXCEPTION 'Expected no existing candidate cards';
    END IF;
    INSERT INTO public.editorial_cards ({', '.join(GRANTED_COLUMNS)}) VALUES
        {inserts};
    GET DIAGNOSTICS affected = ROW_COUNT;
    IF affected <> {count} THEN RAISE EXCEPTION 'Card insert count failed'; END IF;
    IF (SELECT count(*) FROM public.editorial_cards c
        JOIN (VALUES {expected}) AS x(card_id, fingerprint) ON x.card_id = c.card_id
        WHERE c.owner_id = '{OWNER}' AND public.editorial_content_fingerprint(c) = x.fingerprint
          AND c.status = 'candidate' AND c.approval_id IS NULL AND c.sanitized) <> {count} THEN
        RAISE EXCEPTION 'Card content verification failed';
    END IF;
END $card_insert$;
COMMIT;
"""  # noqa: S608 -- offline SQL artifact; constants and escaped literals only
    report = {'count': count, 'owner_id': OWNER, 'required_role': REQUIRED_ROLE,
              'cards': [{'card_id': card.card_id, 'fingerprint': fp}
                        for card, fp in zip(cards, fingerprints, strict=True)],
              'sql_sha256': hashlib.sha256(sql.encode('utf-8')).hexdigest(),
              'status': 'manual_review_only'}
    return sql, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        directory = Path(args.output_dir)
        paths = [directory / PLAN_NAME, directory / REPORT_NAME]
        if any(path.exists() for path in paths):
            raise SeedError('output_exists')
        sql, report = prepare(load_snapshot(args.snapshot))
        encoded = [sql.encode('utf-8'), (json.dumps(report, ensure_ascii=True, indent=2) + '\n').encode('utf-8')]
        # Exclusive creation: never overwrite. A write failure may leave a partial artifact.
        for path, payload in zip(paths, encoded, strict=True):
            with path.open('xb') as stream:
                stream.write(payload)
        print(json.dumps({'outputs': [{'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest()}
                                     for path, payload in zip(paths, encoded, strict=True)],
                          'count': report['count']}))
        return 0
    except SeedError as error:
        print(str(error))
        return 1
    except Exception:
        print('insert_plan_failed')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
