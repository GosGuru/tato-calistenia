"""Pinned, fiction-only transport smoke. Import and default check are inert."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from ..raw_evaluation import export_bundle, load_bank, result_record

NODE_SHA = '9c9245166b4a8e182e0b797da9c20136117ff24368eaff1fec8343a123c8db0e'
LOCK_SHA = 'a6b9733d7fd66248c2ac2bfeac6913163f62321c921f8ff3d7f140746b77e391'
VERSION = '0.123.1'
GUARD = Path(__file__).with_name('deny_network.cjs').resolve()
MAX_REPORT = 8_000_000
PREFIX = 'TATO_FENCE '
SAFE_FAILURES = frozenset({
    'Runtime pin mismatch', 'Runtime metadata mismatch', 'Required runtime file missing',
    'LOCALAPPDATA missing', 'Invalid bounded JSON file', 'Expected exactly five fictional cases',
    'Report counts mismatch', 'Report row count mismatch', 'Report identity or output mismatch',
    'Report prompt mismatch', 'Invalid report schema', 'Fence diagnostics exceeded bound',
    'Malformed fence marker', 'Fence startup marker missing', 'Malformed fence attempt',
    'Invalid fence API', 'Invalid fence destination', 'Invalid fence callsite',
    'Unexpected fence marker', 'Fence exit marker missing', 'Fence counters mismatch',
    'Forbidden process, worker or server attempt', 'Pinned CLI timed out; no retry',
    'Pinned CLI failed; framework output withheld', 'Pinned CLI version mismatch',
    'Missing or oversized report',
})


def runtime_base():
    value = os.environ.get('LOCALAPPDATA')
    if not value:
        raise ValueError('LOCALAPPDATA missing')
    return Path(value) / 'TatoEditorialEval'


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    try:
        if path.stat().st_size > MAX_REPORT:
            raise ValueError('JSON exceeds bound')
        with path.open('rb') as stream:
            raw = stream.read(MAX_REPORT + 1)
        if len(raw) > MAX_REPORT:
            raise ValueError('JSON exceeds bound')
        return json.loads(raw.decode('utf-8'))
    except (OSError, ValueError, RecursionError):
        raise ValueError('Invalid bounded JSON file') from None


def check_runtime(base=None):
    """Read only fixed runtime artifacts; no CLI invocation or profile reads."""
    base = Path(base) if base is not None else runtime_base()
    node = base / 'node-v22.23.3-win-x64/node.exe'
    package = base / 'promptfoo-0.123.1'
    cli = package / 'node_modules/promptfoo/dist/src/entrypoint.js'
    if file_hash(node) != NODE_SHA or file_hash(package / 'package-lock.json') != LOCK_SHA:
        raise ValueError('Runtime pin mismatch')
    root = read_json(package / 'package.json')
    installed = read_json(package / 'node_modules/promptfoo/package.json')
    if root.get('dependencies', {}).get('promptfoo') != VERSION or installed.get('version') != VERSION:
        raise ValueError('Runtime metadata mismatch')
    if not cli.is_file() or not GUARD.is_file():
        raise ValueError('Required runtime file missing')
    return {'base': base, 'node': node, 'cli': cli}


def isolated_env(root):
    """Whitelist OS essentials, never inherit credentials, proxies or loaders."""
    env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'COMSPEC') if key in os.environ}
    for key, suffix in {
        'HOME': 'home', 'USERPROFILE': 'home', 'APPDATA': 'appdata',
        'LOCALAPPDATA': 'local', 'TEMP': 'temp', 'TMP': 'temp',
        'XDG_CONFIG_HOME': 'config', 'XDG_CACHE_HOME': 'cache', 'XDG_STATE_HOME': 'state',
        'PROMPTFOO_CONFIG_DIR': 'config', 'PROMPTFOO_CACHE_PATH': 'cache',
        'PROMPTFOO_LOG_DIR': 'logs',
    }.items():
        env[key] = str(root / suffix)
    env.update(dict.fromkeys(('PROMPTFOO_DISABLE_TELEMETRY', 'PROMPTFOO_DISABLE_UPDATE',
                              'PROMPTFOO_DISABLE_SHARING', 'PROMPTFOO_DISABLE_DEBUG_LOG',
                              'PROMPTFOO_DISABLE_ERROR_LOG', 'PYTHONDONTWRITEBYTECODE'), '1'))
    env.update({'NO_COLOR': '1', 'CI': '1'})
    return env


def prepare_bundle():
    cases, expectations, _ = load_bank()
    if len(cases) != 5:
        raise ValueError('Expected exactly five fictional cases')
    records = [result_record(case, json.dumps({'type': 'dm', 'text': 'MOCK_IMPORT_ONLY ' + case.id}, separators=(',', ':')))
               for case in cases]
    bundle = export_bundle(cases, expectations, records)
    bundle['config']['sharing'] = False
    return bundle


def validate_report(report, bundle):
    """Verify transport only, never infer a quality score from JSON validity."""
    try:
        summary = report['results']
        stats = summary['stats']
        if any(type(stats[key]) is not int or stats[key] != expected
               for key, expected in (('successes', 5), ('failures', 0), ('errors', 0))):
            raise ValueError('Report counts mismatch')
        rows = summary['results']
        tests = bundle['config']['tests']
        if type(rows) is not list or len(rows) != 5:
            raise ValueError('Report row count mismatch')
        for index, (row, expected) in enumerate(zip(rows, tests, strict=True)):
            actual = row['testCase']
            if (type(row['testIdx']) is not int or row['testIdx'] != index or type(row['success']) is not bool
                    or not row['success'] or row.get('error')
                    or actual['description'] != expected['description']
                    or actual['vars'] != expected['vars']
                    or actual['providerOutput'] != expected['providerOutput']
                    or not actual['providerOutput']
                    or row['response']['output'] != expected['providerOutput']):
                raise ValueError('Report identity or output mismatch')
            if 'prompt' in row and row['prompt']['raw'] != expected['vars']['raw_prompt']:
                raise ValueError('Report prompt mismatch')
    except (KeyError, TypeError, IndexError):
        raise ValueError('Invalid report schema') from None


def guard_evidence(stderr, require_exit=True):
    """Only retain schema-checked fence metadata, never framework diagnostics."""
    if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8', errors='replace')
    events = []
    for line in (stderr or '').splitlines():
        if not line.startswith(PREFIX):
            continue
        if len(line) > 16000 or len(events) >= 130:
            raise ValueError('Fence diagnostics exceeded bound')
        try:
            event = json.loads(line[len(PREFIX):])
        except ValueError:
            raise ValueError('Malformed fence marker') from None
        if type(event) is not dict:
            raise ValueError('Malformed fence marker')
        events.append(event)
    if not events or events[0] != {'event': 'startup', 'version': 1}:
        raise ValueError('Fence startup marker missing')
    attempts = []
    for event in events[1:]:
        if event.get('event') == 'blocked':
            if (set(event) != {'event', 'api', 'destination', 'callsite'}
                    or any(type(event[key]) is not str for key in ('api', 'destination', 'callsite'))):
                raise ValueError('Malformed fence attempt')
            if not re.fullmatch(r'[a-zA-Z0-9_.]{1,100}', event['api']):
                raise ValueError('Invalid fence API')
            if not re.fullmatch(r'(?:https?://)?[a-zA-Z0-9.\[\]:-]{1,180}', event['destination']):
                raise ValueError('Invalid fence destination')
            if not re.fullmatch(r'(?:unavailable|node_modules/(?:@[\w.-]+/)?[\w./-]+:\d+)', event['callsite']):
                raise ValueError('Invalid fence callsite')
            attempts.append(event)
        elif event.get('event') != 'exit':
            raise ValueError('Unexpected fence marker')
    end = events[-1]
    if require_exit:
        if set(end) != {'event', 'total', 'forbidden', 'counts'} or end['event'] != 'exit':
            raise ValueError('Fence exit marker missing')
        if (type(end['total']) is not int or type(end['forbidden']) is not int
                or type(end['counts']) is not dict
                or any(not re.fullmatch(r'[a-zA-Z0-9_.]{1,100}', key) or type(value) is not int or value < 1
                       for key, value in end['counts'].items())
                or sum(end['counts'].values()) != end['total']
                or len(attempts) != min(end['total'], 128)):
            raise ValueError('Fence counters mismatch')
        if end['forbidden'] or any(event['destination'] == 'withheld' for event in attempts):
            raise ValueError('Forbidden process, worker or server attempt')
    return {'attempts': attempts, 'counters': end if require_exit else None}


def run_mode(mode, base=None):
    if mode not in ('probe', 'smoke'):
        raise ValueError('Unsupported mode')
    runtime = check_runtime(base)
    fixture_parent = runtime['base'] / 'tmp'
    fixture_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='promptfoo-smoke-', dir=fixture_parent) as temporary:
        root = Path(temporary)
        env = isolated_env(root)
        for name in ('home', 'appdata', 'local', 'temp', 'config', 'cache', 'state', 'logs'):
            (root / name).mkdir()
        command = [str(runtime['node']), '--require', str(GUARD), str(runtime['cli'])]
        bundle = None
        report_path = root / 'report.json'
        if mode == 'probe':
            command += ['--version']
        else:
            bundle = prepare_bundle()
            config_path = root / 'promptfooconfig.json'
            config_path.write_text(json.dumps(bundle['config'], ensure_ascii=True), encoding='utf-8')
            command += ['eval', '--config', str(config_path), '--output', str(report_path),
                        '--max-concurrency', '1', '--no-write', '--no-cache', '--no-table',
                        '--no-progress-bar', '--no-share']
        try:
            completed = subprocess.run(command, shell=False, cwd=root, env=env,
                                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                                       timeout=120 if mode == 'probe' else 180)
        except subprocess.TimeoutExpired as error:
            try:
                print(json.dumps(guard_evidence(error.stderr, require_exit=False)))
            except ValueError:
                print('Fence diagnostics unavailable')
            raise ValueError('Pinned CLI timed out; no retry') from None
        try:
            evidence = guard_evidence(completed.stderr)
        except ValueError:
            print(json.dumps(guard_evidence(completed.stderr, require_exit=False), ensure_ascii=True))
            raise
        print(json.dumps(evidence, ensure_ascii=True))
        print(json.dumps({'stage': 'cli-exit', 'returncode': completed.returncode}))
        if completed.returncode != 0:
            raise ValueError('Pinned CLI failed; framework output withheld')
        if mode == 'probe':
            if VERSION not in completed.stdout.splitlines():
                raise ValueError('Pinned CLI version mismatch')
        else:
            if not report_path.is_file() or report_path.stat().st_size > MAX_REPORT:
                raise ValueError('Missing or oversized report')
            validate_report(read_json(report_path), bundle)
        return {'mode': mode, 'transport': 'passed', 'model': 'unknown', 'effort': 'unknown',
                'guidance': 'off', 'quality': 'not-evaluated', 'blocked': evidence['counters']['total']}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Pinned fictional transport check; no inference.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--probe-startup', action='store_true')
    mode.add_argument('--smoke', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.probe_startup or args.smoke:
            result = run_mode('probe' if args.probe_startup else 'smoke')
        else:
            check_runtime()
            _, _, manifest = load_bank()
            result = {'runtime': VERSION, 'node_sha256': NODE_SHA, 'lock_sha256': LOCK_SHA,
                      'bank': manifest, 'execution': 'not-run'}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (ValueError, OSError, RecursionError) as error:
        reason = str(error) if str(error) in SAFE_FAILURES else 'Unclassified validation failure'
        print(json.dumps({'status': 'failed-closed', 'reason': reason, 'retry': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
