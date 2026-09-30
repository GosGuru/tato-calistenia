"""Small offline RAW evaluation bank. No inference, persistence or live runner."""
import argparse
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .raw_history import RawHistoryPacket, parse_raw_result, raw_prompt
from .real_history import RULE_PATHS, load_real_rules

BANK = Path(__file__).resolve().parent / 'evaluation'
ROOT = Path(__file__).resolve().parents[2]
ID = re.compile(r'[a-z][a-z0-9-]{0,63}')


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_json(path):
    """Read local bank declarations; duplicate keys are never silently accepted."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate bank key')
            result[key] = value
        return result

    raw = path.read_bytes()
    if len(raw) > 1_000_000:
        raise ValueError('Bank file too large')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
    except (ValueError, RecursionError):
        raise ValueError('Invalid bank JSON') from None


@dataclass(frozen=True)
class CasePacket:
    id: str
    packet: RawHistoryPacket
    prompt: str
    fingerprint: str


def build_cases(inputs, current_rules):
    """Pure packet construction; no expectations argument or inferred case state."""
    if type(inputs) is not list or not 4 <= len(inputs) <= 6:
        raise ValueError('Expected four to six fictional cases')
    cases, seen = [], set()
    for item in inputs:
        if (type(item) is not dict or set(item) != {'id', 'history'}
                or type(item['id']) is not str or not ID.fullmatch(item['id'])
                or item['id'] in seen):
            raise ValueError('Invalid input case')
        seen.add(item['id'])
        packet = RawHistoryPacket(item['history'], current_rules, True, guidance=())
        prompt = raw_prompt(packet)
        cases.append(CasePacket(item['id'], packet, prompt, sha256(prompt)))
    return tuple(cases)


def validate_cases(cases):
    if (type(cases) is not tuple or not 4 <= len(cases) <= 6
            or any(type(case) is not CasePacket or type(case.packet) is not RawHistoryPacket
                   for case in cases)):
        raise ValueError('Invalid case packets')
    rebuilt = build_cases([{'id': c.id, 'history': c.packet.history} for c in cases],
                          cases[0].packet.current_rules)
    if cases != rebuilt:
        raise ValueError('Case payload or fingerprint mismatch')


def validate_expectations(cases, expectations):
    if type(expectations) is not list or len(expectations) != len(cases):
        raise ValueError('Invalid expectations')
    for case, item in zip(cases, expectations, strict=True):
        if (type(item) is not dict or set(item) != {'id', 'type', 'criteria'}
                or item['id'] != case.id or item['type'] not in ('dm', 'needs_context')
                or type(item['criteria']) is not list or not item['criteria']
                or any(type(value) is not str or not value.strip() for value in item['criteria'])):
            raise ValueError('Invalid expectations or order')


def load_bank():
    """Read only fixed fictional inputs, separate expectations and seven full rules."""
    rules = load_real_rules()
    contents = [(path, (ROOT / path).read_bytes()) for path in RULE_PATHS]
    if len(contents) != 7 or '\n\n'.join(raw.decode('utf-8') for _, raw in contents) != rules:
        raise ValueError('Rule snapshot mismatch')
    cases = build_cases(read_json(BANK / 'inputs.json'), rules)
    expectations = read_json(BANK / 'expectations.json')
    validate_expectations(cases, expectations)
    manifest = {
        'version': 1,
        'mode': 'offline-check',
        'guidance': 'off',
        'model': 'unknown',
        'effort': 'unknown',
        'results': 'not-run',
        'rules_sha256': sha256(rules),
        'sources': [{'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                    for path, raw in contents],
        'cases': [{'id': c.id, 'fingerprint': c.fingerprint,
                   'prompt_bytes': len(c.prompt.encode('utf-8'))} for c in cases],
    }
    return cases, expectations, manifest


def result_record(case, output):
    """Bind an existing synthetic output to its exact prompt; never generate it."""
    if (type(case) is not CasePacket or raw_prompt(case.packet) != case.prompt
            or sha256(case.prompt) != case.fingerprint or case.packet.guidance != ()):
        raise ValueError('Invalid case packet')
    parse_raw_result(output)
    return {'id': case.id, 'fingerprint': case.fingerprint, 'output': output}


def export_bundle(cases, expectations, records):
    """Return config, list[str] outputs and separate review criteria, only in memory.

    Records must retain bank order and exact prompt fingerprints. Schema validity
    is not a semantic verdict; expected result types are for independent review.
    """
    validate_cases(cases)
    validate_expectations(cases, expectations)
    if type(records) is not list or len(records) != len(cases):
        raise ValueError('Invalid result records')
    outputs = []
    for case, record in zip(cases, records, strict=True):
        if (type(record) is not dict or set(record) != {'id', 'fingerprint', 'output'}
                or record['id'] != case.id or record['fingerprint'] != case.fingerprint):
            raise ValueError('Result identity, order or fingerprint mismatch')
        parse_raw_result(record['output'])
        outputs.append(record['output'])
    return {
        'config': {
            'description': 'Offline fictional RAW outputs; structural checks only',
            'prompts': ['{{raw_prompt}}'],
            'providers': ['python:' + (BANK / 'no_inference_provider.py').as_posix()],
            'tests': [{'description': c.id, 'vars': {'raw_prompt': c.prompt},
                       'providerOutput': output,
                       'assert': [{'type': 'is-json'}]}
                      for c, output in zip(cases, outputs, strict=True)],
        },
        'outputs': outputs,
        'expectations': copy.deepcopy(expectations),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate the fictional RAW bank without inference or writes.')
    parser.add_argument('--check', action='store_true', help='Validate and print manifest (also the default)')
    parser.parse_args(argv)
    try:
        _, _, manifest = load_bank()
    except (ValueError, OSError, RecursionError):
        print('Invalid offline bank')
        return 1
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
