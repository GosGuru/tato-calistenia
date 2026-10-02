"""Paired-run voice evaluation harness: pure logic plus the synthetic case bank.

This module compares one already-produced baseline output against one already-produced
guided output for the same case and reports deterministic signals for a human scorer. It
never calls a model: outputs enter as RAW result strings (the closed union accepted by
``raw_history.parse_raw_result``), so a later slice can drive it with the existing
``create_runner`` / ``ApiSessionRunner`` while this module stays inference-free. There is
no LLM-as-judge anywhere (``evaluation/README.md``: "sin juez LLM"; ``casos-calibracion.md``:
"No hay integración automática de proveedor ni evaluador semántico").

What the report is and is not
-----------------------------

The report is JSON-serializable and hands signals to a human scorer; it never emits a
pass/fail verdict of its own. Semantic diagnosis (diagnosis, prescribing, promise, pressure
via family/health/shame, repeating a confirmed fact, premature call) is NOT detected here:
those hard fails live in the human rubric. See ``voice_signals`` for the full
structural/semantic boundary.

The rubric slot keeps the exact meaning of ``casos-calibracion.md`` "Rúbrica": score each
output 0-2 on ``fidelidad``, ``fase``, ``naturalidad``, ``posicionamiento`` and
``seguridad``, plus the ``intencion`` semantic gate, which has no score compensation.
Field docs are copied from that section verbatim; do not paraphrase them.

Provenance: ``model``, ``effort`` and ``guidance`` follow the offline bank placeholders
(``'unknown'``, ``'unknown'``, ``'off'``). A real paired run replaces them with the observed
values and keeps model and effort fixed across both conditions ("Mantener modelo y esfuerzo
fijos para comparar antes/después; declarar los valores reales o desconocidos").

The case bank (``evaluation/voice_cases.json``) is fictional and sanitized. Its
``expected_move`` entries are decision statements, never DM answers to copy, and its
``forbidden`` entries are scorer guidance, deliberately not an automated matcher: the
rubric says "No evaluar por palabras prohibidas". Draft texts are inputs only; the returned
structures carry signals, counts and case identity, never draft text.
"""
import json
import re
from pathlib import Path

if __package__:
    from .raw_history import parse_raw_result, valid_raw_text
    from .voice_signals import mirror, repetition, skeleton_reuse, structural_fails
else:
    from raw_history import parse_raw_result, valid_raw_text
    from voice_signals import mirror, repetition, skeleton_reuse, structural_fails

BANK = Path(__file__).resolve().parent / 'evaluation' / 'voice_cases.json'
CASE_FIELDS = {'id', 'history', 'failure_pattern', 'expected_move', 'forbidden'}
PAIR_FIELDS = {'case', 'baseline', 'guided', 'skeleton_reuse', 'delta'}
ID = re.compile(r'[a-z][a-z0-9-]{0,63}')
LEAD_LABEL = 'Prospecto:'
AGENT_LABEL = 'Tato:'

FAILURE_PATTERNS = (
    'emotional_effort_opening',
    'deep_personal_opening',
    'terse_lead',
    'informal_register',
    'reentry_after_days',
    'specific_doubt',
)

# Verbatim field meanings from casos-calibracion.md "Rúbrica"; the report copies them.
RUBRIC_DOCS = {
    'fidelidad': 'usa el historial sin inventar ni repetir',
    'fase': ('ejecuta el movimiento correcto y no reabre evidencia suficiente '
             'por el último detalle técnico'),
    'naturalidad': ('responde a la persona con continuidad, directividad y reconocimiento '
                    'proporcionales, sin narrar la calificación ni anunciar trabajo conjunto '
                    'no acordado'),
    'posicionamiento': 'conecta calistenia con el destino sin brochure',
    'seguridad': 'respeta salud, privacidad y límites comerciales',
    'intencion': ('es una condición semántica obligatoria, sin compensación por puntaje: '
                  'el movimiento aporta una distinción útil, resuelve algo concreto o abre '
                  'evidencia que cambia una decisión pendiente. Eco más pregunta vaga no '
                  'aprueba; una pregunta directa necesaria sí puede hacerlo sin cue ni '
                  'prefacio. Al presentar ruta, debe entenderse la relación entre la brecha '
                  'y la función de una ayuda real, no solo una promesa de orden o adaptación.'),
}


def read_json(path):
    """Read local bank declarations; duplicate keys are never silently accepted."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate bank key')
            result[key] = value
        return result

    raw = Path(path).read_bytes()
    if len(raw) > 1_000_000:
        raise ValueError('Bank file too large')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
    except (ValueError, RecursionError):
        raise ValueError('Invalid bank JSON') from None


def split_history(history):
    """Split the labeled raw history into the lead's and the assistant's message texts.

    Each message is one line labeled ``Prospecto:`` or ``Tato:``. Unlabeled lines (export
    headers, date markers) are ignored, so a dated re-entry keeps its pause in ``history``
    without becoming a message.
    """
    if type(history) is not str:
        raise ValueError('Invalid history')
    leads, agents = [], []
    for line in history.splitlines():
        if line.startswith(LEAD_LABEL):
            leads.append(line[len(LEAD_LABEL):].strip())
        elif line.startswith(AGENT_LABEL):
            agents.append(line[len(AGENT_LABEL):].strip())
    return tuple(leads), tuple(agents)


def validate_case(item):
    """Validate one fictional case and return a shallow copy; no expectations, no state."""
    if type(item) is not dict or set(item) != CASE_FIELDS:
        raise ValueError('Invalid voice case')
    if type(item['id']) is not str or not ID.fullmatch(item['id']):
        raise ValueError('Invalid case id')
    if not valid_raw_text(item['history']):
        raise ValueError('Invalid case history')
    leads, agents = split_history(item['history'])
    if not leads or not agents:
        raise ValueError('Case history needs labeled lead and assistant messages')
    if item['failure_pattern'] not in FAILURE_PATTERNS:
        raise ValueError('Unknown failure pattern')
    if type(item['expected_move']) is not str or not item['expected_move'].strip():
        raise ValueError('Invalid expected move')
    forbidden = item['forbidden']
    if (type(forbidden) is not list or not forbidden
            or any(type(value) is not str or not value.strip() for value in forbidden)):
        raise ValueError('Invalid forbidden list')
    return {'id': item['id'], 'history': item['history'],
            'failure_pattern': item['failure_pattern'], 'expected_move': item['expected_move'],
            'forbidden': list(forbidden)}


def parse_cases(items):
    """Validate the bank: exactly six cases, unique ids, one case per failure pattern."""
    if type(items) is not list or len(items) != 6:
        raise ValueError('Expected exactly six voice cases')
    cases, seen = [], set()
    for item in items:
        case = validate_case(item)
        if case['id'] in seen:
            raise ValueError('Duplicate case id')
        seen.add(case['id'])
        cases.append(case)
    if set(FAILURE_PATTERNS) != {case['failure_pattern'] for case in cases}:
        raise ValueError('The bank must cover each failure pattern exactly once')
    return tuple(cases)


def load_cases(path=BANK):
    """Read only the fixed fictional case bank; no rules, expectations or persistence."""
    return parse_cases(read_json(path))


def _draft_text(result):
    """The message text of a parsed RAW result; a clarification keeps its question text."""
    return result['text'] if result['type'] == 'dm' else result['question']


def _output_signals(draft, lead_text, earlier):
    signals = repetition(draft, earlier)
    return {
        'mirror': mirror(draft, lead_text),
        'repetition': {'opening_reused': signals.opening_reused,
                       'question_reused': signals.question_reused,
                       'shared_trigrams': signals.shared_trigrams},
        'structural_fails': structural_fails(draft),
    }


def _delta(baseline, guided):
    """guided minus baseline; positive mirror = more lead vocabulary, other positives = more reuse or violations."""
    return {
        'mirror': round(guided['mirror'] - baseline['mirror'], 3),
        'repetition': {key: guided['repetition'][key] - baseline['repetition'][key]
                       for key in baseline['repetition']},
        'structural_fails': {
            key: guided['structural_fails'][key] - baseline['structural_fails'][key]
            for key in baseline['structural_fails']},
    }


def compare_pair(case, baseline_output, guided_output):
    """Signals for both already-produced outputs plus deltas; no inference and no verdict.

    Both outputs must already exist as RAW result strings and are validated with
    ``raw_history.parse_raw_result`` first; anything that fails is rejected with
    ``ValueError``. ``skeleton_reuse`` is pairwise by construction (symmetric), so it is
    reported once per pair and has no delta. The case's history is not duplicated here:
    ``case.id`` points at the bank entry.
    """
    validated = validate_case(case)
    baseline = parse_raw_result(baseline_output)
    guided = parse_raw_result(guided_output)
    leads, earlier = split_history(validated['history'])
    lead_text = '\n'.join(leads)
    baseline_signals = _output_signals(_draft_text(baseline), lead_text, earlier)
    guided_signals = _output_signals(_draft_text(guided), lead_text, earlier)
    return {
        'case': {'id': validated['id'], 'failure_pattern': validated['failure_pattern'],
                 'expected_move': validated['expected_move'],
                 'forbidden': validated['forbidden']},
        'baseline': baseline_signals,
        'guided': guided_signals,
        'skeleton_reuse': skeleton_reuse(_draft_text(baseline), _draft_text(guided)),
        'delta': _delta(baseline_signals, guided_signals),
    }


def _rubric_slot():
    return dict.fromkeys(RUBRIC_DOCS)


def build_report(pairs, model='unknown', effort='unknown', guidance='off'):
    """JSON-serializable paired-run report with an explicit human rubric slot.

    The report never emits a pass/fail verdict: it carries the deterministic signals and
    leaves every ``human_scores`` slot empty for the scorer. Each slot has exactly the
    fields of ``casos-calibracion.md`` "Rúbrica" (0-2 each plus the ``intencion`` gate),
    and ``rubric.fields`` carries their verbatim meanings.
    """
    if type(pairs) is not list or any(
            type(pair) is not dict or set(pair) != PAIR_FIELDS for pair in pairs):
        raise ValueError('Invalid pair list')
    if any(type(value) is not str or not value.strip() for value in (model, effort, guidance)):
        raise ValueError('Invalid provenance')
    return {
        'version': 1,
        'mode': 'paired-voice-eval',
        'model': model,
        'effort': effort,
        'guidance': guidance,
        'rubric': {
            'fields': {name: {'scale': 'gate' if name == 'intencion' else '0-2', 'doc': doc}
                       for name, doc in RUBRIC_DOCS.items()},
            'note': ('Human scorer fills every human_scores slot following '
                     'casos-calibracion.md "Rúbrica"; the harness reports signals only.'),
        },
        'pairs': [dict(pair, human_scores={'baseline': _rubric_slot(),
                                           'guided': _rubric_slot()})
                  for pair in pairs],
    }
