"""Offline tests: no model inference, no network and no database call happens here.

The tool reads a local snapshot and writes one plan plus one report. These tests
parse the generated SQL as text and reconcile every literal against the card
content; nothing connects anywhere and no artifact is ever executed.
"""
import ast
import copy
import hashlib
import json
import re
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from tools.editorial_rag import (  # pyright: ignore[reportMissingImports]
    prepare_card_insert as insert,
)
from tools.editorial_rag import (  # pyright: ignore[reportMissingImports]
    prepare_card_seed as seed,
)

# The eleven columns of the column-scoped insert grant in 001_editorial_cards.sql,
# transcribed here independently so the plan is checked against the grant itself.
GRANTED_COLUMNS = ('owner_id', 'card_id', 'provenance_id', 'sanitized', 'phase', 'gate',
                   'situation', 'last_assistant_move', 'proposed_move', 'positive_voice',
                   'negative_repetition')
SEED_PLAN_DIR = Path(__file__).resolve().parent / 'app_rules' / 'seed-plan'
QUOTE_SITUATION = "Aplica cuando dice it's fine (en serio); no aplica cuando miente."


def build_cards(count, quote=False):
    return [seed.Card(
        card_id=f'fixture_card_{index:02d}', provenance_id='fictional_fixture',
        status='candidate', sanitized=True, phase='ruta',
        gate='fictional_gate',
        situation=QUOTE_SITUATION if quote else f'Invented puzzle scenario {index}.',
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


def expected_row(card):
    """The exact expected INSERT VALUES token stream for one card."""
    return [('text', seed.OWNER), ('text', card.card_id), ('text', card.provenance_id),
            ('word', 'TRUE'), ('text', card.phase), ('text', card.gate),
            ('text', card.situation), ('text', card.last_assistant_move),
            ('text', card.proposed_move), ('text', card.positive_voice),
            ('text', card.negative_repetition)]


def parse_value_tuples(text):
    """Parse SQL VALUES tuples into rows of ('text'|'word', value) tokens.

    A 'text' token is unescaped by the SQL rule (doubled quotes collapse to one);
    a 'word' token is a bare keyword such as the pinned TRUE. Semicolons, commas
    and parentheses inside literals never terminate a token or a tuple, so an
    escaped quote cannot corrupt the row or literal counts.
    """
    rows, current, depth, index = [], None, 0, 0
    while index < len(text):
        char = text[index]
        if char == "'":
            index += 1
            value = []
            while index < len(text):
                if text[index] != "'":
                    value.append(text[index])
                    index += 1
                elif text[index:index + 2] == "''":
                    value.append("'")
                    index += 2
                else:
                    index += 1
                    break
            else:
                raise AssertionError('unterminated SQL literal')
            if current is None:
                raise AssertionError('literal outside a VALUES tuple')
            current.append(('text', ''.join(value)))
            continue
        elif char.isalpha():
            start = index
            while index < len(text) and text[index].isalpha():
                index += 1
            if current is None:
                raise AssertionError('word outside a VALUES tuple')
            current.append(('word', text[start:index]))
            continue
        elif char == '(':
            depth += 1
            if depth == 1:
                current = []
        elif char == ')':
            depth -= 1
            if depth == 0:
                rows.append(current)
                current = None
        elif char == ';' and depth == 0:
            break
        index += 1
    return rows


def count_literals(text):
    """Count every well-formed single-quoted literal in the whole plan."""
    count, index = 0, 0
    while index < len(text):
        if text[index] != "'":
            index += 1
            continue
        index += 1
        while index < len(text):
            if text[index] != "'":
                index += 1
            elif text[index:index + 2] == "''":
                index += 2
            else:
                index += 1
                count += 1
                break
        else:
            raise AssertionError('unterminated SQL literal')
    return count


def parse_insert(sql):
    match = re.search(r'INSERT INTO public\.editorial_cards \(([^)]*)\) VALUES\s', sql, re.S)
    assert match is not None, 'INSERT statement not found'
    columns = tuple(name.strip() for name in match.group(1).split(','))
    return columns, parse_value_tuples(sql[match.end():])


def parse_verification(sql):
    match = re.search(r'JOIN \(VALUES (.*?)\) AS x\(card_id, fingerprint\)', sql, re.S)
    assert match is not None, 'content verification VALUES list not found'
    return parse_value_tuples(match.group(1))


class InsertPlanTests(unittest.TestCase):
    def test_accepts_one_two_and_twelve_cards_with_consistent_plan_and_report(self):
        for count in (1, 2, 12):
            with self.subTest(count=count):
                cards = build_cards(count)
                sql, report = insert.prepare(snapshot_for(cards))
                self.assertEqual(report['count'], count)
                self.assertEqual(set(report), {'count', 'owner_id', 'required_role', 'cards',
                                               'sql_sha256', 'status'})
                self.assertEqual(report['owner_id'], seed.OWNER)
                self.assertEqual(report['status'], 'manual_review_only')
                self.assertEqual(report['sql_sha256'], hashlib.sha256(sql.encode('utf-8')).hexdigest())
                self.assertIn('bypassrls', report['required_role'].lower())
                self.assertEqual(len(report['cards']), count)
                self.assertEqual(list(report['cards'][0]), ['card_id', 'fingerprint'])
                derived = {card.card_id: seed.fingerprint(seed.OWNER, card) for card in cards}
                self.assertEqual({row['card_id']: row['fingerprint'] for row in report['cards']}, derived)
                # Warning header in the seed plan style, naming the BYPASSRLS role.
                self.assertTrue(sql.startswith('-- Manual review only; this plan is not authorization'))
                header = sql.split('BEGIN;', 1)[0]
                self.assertIn('Manual review only', header)
                self.assertIn('this plan is not authorization', header)
                self.assertIn('BYPASSRLS', header)
                self.assertIn('postgres', header)
                self.assertIn('service_role', header)
                # One transaction, one DO block, lock first, no upsert escape hatch.
                self.assertEqual(sql.count('BEGIN;'), 1)
                self.assertTrue(sql.endswith('COMMIT;\n'))
                self.assertEqual(sql.count('DO $'), 1)
                self.assertEqual(sql.count('END $card_insert$;'), 1)
                self.assertIn('DO $card_insert$\nDECLARE affected integer;\nBEGIN\n'
                              '    LOCK TABLE public.editorial_cards IN SHARE ROW EXCLUSIVE MODE;', sql)
                self.assertNotIn('ON CONFLICT', sql)
                self.assertNotIn('EXECUTE', sql)
                # The report carries no card prose at all.
                report_text = json.dumps(report)
                for card in cards:
                    for prose in (card.situation, card.positive_voice, card.negative_repetition):
                        self.assertNotIn(prose, report_text)

    def test_insert_column_list_omits_status_and_approval_id(self):
        self.assertEqual(insert.GRANTED_COLUMNS, GRANTED_COLUMNS)
        for count in (1, 2, 12):
            with self.subTest(count=count):
                sql, _ = insert.prepare(snapshot_for(build_cards(count)))
                columns, rows = parse_insert(sql)
                # Parsed column list of the single INSERT, never a substring scan.
                self.assertEqual(columns, GRANTED_COLUMNS)
                self.assertNotIn('status', columns)
                self.assertNotIn('approval_id', columns)
                self.assertEqual(sql.count('INSERT INTO'), 1)
                self.assertEqual(len(rows), count)
                for row in rows:
                    self.assertEqual(len(row), len(columns))
                # The omitted pair is still read by the verification guard, so its
                # absence above is a real omission and not a missing feature.
                self.assertIn("c.status = 'candidate'", sql)
                self.assertIn('c.approval_id IS NULL', sql)

    def test_content_verification_and_insert_count_guards_scale_to_n(self):
        for count in (1, 2, 12):
            with self.subTest(count=count):
                cards = build_cards(count)
                sql, report = insert.prepare(snapshot_for(cards))
                # Insert count guard: N rows, nothing more and nothing less.
                self.assertIn(f"IF affected <> {count} THEN RAISE EXCEPTION 'Card insert count failed'", sql)
                self.assertEqual(sql.count('Card insert count failed'), 1)
                # Content verification guard before commit: N (card_id, fingerprint)
                # pairs joined against the inserted rows, exactly N matches required.
                rows = parse_verification(sql)
                self.assertEqual(len(rows), count)
                self.assertEqual([tuple(value for _, value in row) for row in rows],
                                 [(row['card_id'], row['fingerprint']) for row in report['cards']])
                self.assertRegex(sql, rf"\) <> {count} THEN\s+RAISE EXCEPTION 'Card content verification failed'")
                self.assertEqual(sql.count('Card content verification failed'), 1)
                # Each fingerprint lives only in the verification list; each card id
                # appears in the existence list, the INSERT row and the verification.
                for card, row in zip(cards, report['cards'], strict=True):
                    self.assertEqual(sql.count(row['fingerprint']), 1)
                    self.assertEqual(sql.count(card.card_id), 3)

    def test_existing_cards_fail_closed_before_insert(self):
        cards = build_cards(2)
        sql, _ = insert.prepare(snapshot_for(cards))
        self.assertIn('IF EXISTS (SELECT 1 FROM public.editorial_cards c', sql)
        self.assertIn('RAISE EXCEPTION \'Expected no existing candidate cards\'', sql)
        exists_block = sql.split('INSERT INTO', 1)[0]
        for card in cards:
            self.assertIn("'" + card.card_id + "'", exists_block)
        self.assertLess(exists_block.index('IF EXISTS'), exists_block.index('RAISE EXCEPTION'))

    def test_single_quote_escaping_and_literal_reconciliation(self):
        for count in (1, 2):
            for quote in (True, False):
                with self.subTest(count=count, quote=quote):
                    cards = build_cards(count, quote=quote)
                    sql, _ = insert.prepare(snapshot_for(cards))
                    columns, rows = parse_insert(sql)
                    self.assertEqual(len(rows), count)
                    self.assertEqual(list(rows), [expected_row(card) for card in cards])
                    if quote:
                        escaped = QUOTE_SITUATION.replace("'", "''")
                        self.assertIn("'" + escaped + "'", sql)
                        self.assertNotIn("'" + QUOTE_SITUATION + "'", sql)
                        self.assertGreater(sql.count("''"), 0)
                    # Literal reconciliation across the whole plan: 13 per card
                    # (existence list 1 + INSERT texts 10 + verification pair 2)
                    # plus the two owner constants, the status literal and the
                    # three exception messages.
                    self.assertEqual(count_literals(sql), 13 * count + 6)

    def test_outputs_are_never_overwritten(self):
        for existing in (insert.PLAN_NAME, insert.REPORT_NAME, None):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'snapshot.json'
                snapshot.write_text(json.dumps(snapshot_for(build_cards(2))), encoding='utf-8')
                keep = Path(directory) / (existing or insert.PLAN_NAME)
                keep.write_text('keep', encoding='utf-8')
                with patch('builtins.print'):
                    result = insert.main(['--snapshot', str(snapshot), '--output-dir', directory])
                self.assertEqual(result, 1)
                self.assertEqual(keep.read_text(encoding='utf-8'), 'keep')
                if existing == insert.PLAN_NAME:
                    self.assertFalse((Path(directory) / insert.REPORT_NAME).exists())

    def test_cli_writes_artifacts_once_and_never_again(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'snapshot.json'
            data = snapshot_for(build_cards(12))
            snapshot.write_text(json.dumps(data), encoding='utf-8')
            with patch('builtins.print') as output:
                result = insert.main(['--snapshot', str(snapshot), '--output-dir', directory])
            self.assertEqual(result, 0)
            plan = Path(directory) / insert.PLAN_NAME
            sql = plan.read_text(encoding='utf-8')
            report = json.loads((Path(directory) / insert.REPORT_NAME).read_text(encoding='utf-8'))
            self.assertEqual(report['count'], 12)
            self.assertEqual(report['status'], 'manual_review_only')
            self.assertEqual(report['sql_sha256'], hashlib.sha256(sql.encode('utf-8')).hexdigest())
            self.assertEqual({row['card_id']: row['fingerprint'] for row in report['cards']},
                             data['fingerprints'])
            self.assertEqual(json.loads(output.call_args.args[0])['count'], 12)
            before = (plan.read_bytes(), (Path(directory) / insert.REPORT_NAME).read_bytes())
            with patch('builtins.print'):
                self.assertEqual(insert.main(['--snapshot', str(snapshot), '--output-dir', directory]), 1)
            self.assertEqual((plan.read_bytes(), (Path(directory) / insert.REPORT_NAME).read_bytes()), before)

    def test_tool_never_imports_or_calls_network_or_database_apis(self):
        source = Path(insert.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        roots, names, calls = set(), set(), set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split('.')[0])
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Call):
                calls.add(node.func.id if isinstance(node.func, ast.Name) else
                          node.func.attr if isinstance(node.func, ast.Attribute) else '')
        allowed = {'argparse', 'editorial_criteria', 'hashlib', 'json', 'pathlib',
                   'prepare_card_seed', 'uuid'}
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

    def test_snapshot_contract_is_shared_with_the_seed_tool(self):
        self.assertIs(insert.validate_snapshot, seed.validate_snapshot)
        self.assertIs(insert.load_snapshot, seed.load_snapshot)
        self.assertIs(insert._literal, seed._literal)
        self.assertEqual(insert.OWNER, seed.OWNER)
        source = Path(insert.__file__).read_text(encoding='utf-8')
        # No pinned per-card fingerprint constant may exist in the tool source.
        self.assertIsNone(re.search(r'\b[0-9a-f]{64}\b', source))
        data = snapshot_for(build_cards(2))
        for key, value in [('status', 'approved'), ('approval_id', 'old'), ('sanitized', False),
                           ('owner_id', 'bad'), ('positive_voice', 'changed'), ('count', 3)]:
            mutated = copy.deepcopy(data)
            mutated['cards'][1][key] = value
            with self.subTest(key=key), self.assertRaises(seed.SeedError):
                insert.prepare(mutated)

    def test_fingerprints_link_to_the_seed_plan_artifacts(self):
        data = insert.load_snapshot(SEED_PLAN_DIR / 'snapshot.json')
        sql, report = insert.prepare(data)
        seed_report = json.loads((SEED_PLAN_DIR / 'card-seed-report.json').read_text(encoding='utf-8'))
        produced = {row['card_id']: row['fingerprint'] for row in report['cards']}
        expected = {row['card_id']: row['fingerprint'] for row in seed_report['cards']}
        self.assertEqual(report['count'], seed_report['count'])
        self.assertEqual(produced, expected)
        # Every fingerprint the seed plan's content guards verify must be produced
        # by this insert plan, or the seed plan aborts at approval time.
        seed_sql = (SEED_PLAN_DIR / 'card-seed-plan.sql').read_text(encoding='utf-8')
        guarded = set(re.findall(r"editorial_content_fingerprint\(c\) = '([0-9a-f]{64})'", seed_sql))
        self.assertEqual(guarded, set(produced.values()))
        for card_id, fingerprint_value in produced.items():
            self.assertIn(card_id, sql)
            self.assertIn(fingerprint_value, sql)
        for row in parse_verification(sql):
            self.assertEqual(len(row), 2)


if __name__ == '__main__':
    unittest.main()
